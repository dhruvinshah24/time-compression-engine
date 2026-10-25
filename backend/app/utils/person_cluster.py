"""
Person Cluster & Identity Consolidation Engine.

Resolves track fragmentation and eliminates duplicate personas.
In surveillance footage, single physical subjects are frequently split
into multiple raw tracker tracks due to brief occlusions, posture changes,
or temporary detector dropouts.

This module clusters raw track IDs into unified, verified human personas using:
  1. Strict Temporal Non-Collision: Two tracks overlapping simultaneously
     (>1.0s) cannot represent the same physical person.
  2. Appearance Feature Similarity: Cosine similarity on deep/color embeddings.
  3. Spatial & Temporal Trajectory Linking: Sequential continuity for nearby tracks.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.utils.person_reid import AppearanceEmbedder

logger = logging.getLogger(__name__)


def cluster_tracks_into_persons(
    clips: List[Dict[str, Any]],
    crops_dir: Optional[Path] = None,
    raw_gallery: Optional[Dict[str, Any]] = None,
    similarity_threshold: float = 0.70,
    short_track_threshold: float = 0.62,
    temporal_collision_ms: float = 1200.0,
) -> Tuple[Dict[int, str], Dict[str, Dict[str, Any]]]:
    """
    Cluster raw track IDs into consolidated personas.

    Args:
        clips: List of clip/event dicts from export_manifest or timeline.
        crops_dir: Optional path to directory containing crop JPEGs (*_t{track_id}_*.jpg).
        raw_gallery: Optional existing person_gallery dict to preserve pre-existing labels.
        similarity_threshold: Minimum cosine similarity to merge normal tracks.
        short_track_threshold: Lenient threshold for short tracks (<3s) to prevent over-segmentation.
        temporal_collision_ms: Overlap in ms above which two tracks cannot be the same person.

    Returns:
        (track_to_person, person_gallery)
        - track_to_person: dict mapping int track_id -> "Person N"
        - person_gallery: dict mapping "Person N" -> persona metadata dict
    """
    if not clips:
        return {}, {}

    # 1. Group clips by track_id
    tracks_clips: Dict[int, List[Dict[str, Any]]] = {}
    for c in clips:
        tid = c.get("track_id")
        if tid is not None:
            tracks_clips.setdefault(tid, []).append(c)

    if not tracks_clips:
        return {}, {}

    # 2. Compute time interval and observation metrics for each track
    track_intervals: Dict[int, Tuple[float, float]] = {}
    track_durations_s: Dict[int, float] = {}
    for tid, cl in tracks_clips.items():
        s = min(float(c.get("start_ms", 0)) for c in cl)
        e = max(float(c.get("end_ms", 0)) for c in cl)
        track_intervals[tid] = (s, e)
        track_durations_s[tid] = max(0.1, (e - s) / 1000.0)

    # 3. If raw_gallery already has comprehensive clustering, respect it
    if raw_gallery and len(raw_gallery) > 0:
        existing_track_to_person = {}
        for p_lbl, p_info in raw_gallery.items():
            for tid in p_info.get("track_ids", []):
                existing_track_to_person[tid] = p_lbl

        # If all tracks are covered, return existing
        if all(tid in existing_track_to_person for tid in tracks_clips.keys()):
            return existing_track_to_person, raw_gallery

    # 4. Extract appearance embeddings for each track from crops
    embedder = AppearanceEmbedder()
    track_embeddings: Dict[int, np.ndarray] = {}
    track_best_crop_path: Dict[int, str] = {}

    if crops_dir and crops_dir.exists():
        for tid in tracks_clips.keys():
            # Search for crops with pattern *_t{tid}_*.jpg or {tid}.jpg
            matches = list(crops_dir.glob(f"*_t{tid}_*.jpg"))
            if not matches:
                matches = list(crops_dir.glob(f"*person*_{tid}.jpg"))

            if matches:
                # Pick highest quality / largest file
                best_file = max(matches, key=lambda f: f.stat().st_size)
                track_best_crop_path[tid] = str(best_file)
                try:
                    img = cv2.imread(str(best_file))
                    if img is not None and img.size > 0:
                        track_embeddings[tid] = embedder.compute(img)
                except Exception as exc:
                    logger.debug("[PersonCluster] Failed to read crop %s: %s", best_file, exc)

    # 5. Order tracks by duration and clip count descending (anchor tracks first)
    sorted_tids = sorted(
        tracks_clips.keys(),
        key=lambda tid: (track_durations_s[tid], len(tracks_clips[tid])),
        reverse=True,
    )

    # Clusters structure:
    # {
    #   "label": "Person X",
    #   "track_ids": [tid1, tid2, ...],
    #   "embedding": np.ndarray,
    #   "intervals": [(s1, e1), (s2, e2), ...],
    #   "best_crop_path": str,
    #   "clips": [...],
    # }
    clusters: List[Dict[str, Any]] = []

    for tid in sorted_tids:
        t_start, t_end = track_intervals[tid]
        t_dur = track_durations_s[tid]
        t_emb = track_embeddings.get(tid)
        t_crop = track_best_crop_path.get(tid)

        best_cluster = None
        best_sim = -1.0

        for cluster in clusters:
            # Physical reality check: Two tracks observed simultaneously cannot be the same person!
            collision = False
            for cs, ce in cluster["intervals"]:
                overlap = min(t_end, ce) - max(t_start, cs)
                if overlap > temporal_collision_ms:
                    collision = True
                    break
            if collision:
                continue

            c_emb = cluster["embedding"]
            if t_emb is not None and c_emb is not None:
                sim = float(np.dot(t_emb, c_emb))
                if sim > best_sim:
                    best_sim = sim
                    best_cluster = cluster
            elif t_emb is None and c_emb is None:
                # Fallback when no crops: link if close in time (gap < 4s)
                min_gap = min(
                    abs(t_start - ce) if t_start >= ce else abs(cs - t_end)
                    for cs, ce in cluster["intervals"]
                )
                if min_gap < 4000.0 and best_cluster is None:
                    best_sim = 0.75
                    best_cluster = cluster

        # Lenient threshold for short / fragmented tracks (<3s) to prevent persona explosion
        eff_threshold = short_track_threshold if t_dur < 3.0 else similarity_threshold

        if best_cluster is not None and best_sim >= eff_threshold:
            best_cluster["track_ids"].append(tid)
            best_cluster["intervals"].append((t_start, t_end))
            best_cluster["clips"].extend(tracks_clips[tid])
            if t_emb is not None:
                n = len(best_cluster["track_ids"])
                best_cluster["embedding"] = (best_cluster["embedding"] * (n - 1) + t_emb) / n
                best_cluster["embedding"] /= (np.linalg.norm(best_cluster["embedding"]) + 1e-8)
            if not best_cluster["best_crop_path"] and t_crop:
                best_cluster["best_crop_path"] = t_crop
            logger.debug(
                "[PersonCluster] Track %d (%.1fs) linked to %s (sim=%.3f)",
                tid, t_dur, best_cluster["label"], best_sim,
            )
        else:
            new_label = f"Person {len(clusters) + 1}"
            clusters.append({
                "label": new_label,
                "track_ids": [tid],
                "embedding": t_emb,
                "intervals": [(t_start, t_end)],
                "best_crop_path": t_crop,
                "clips": list(tracks_clips[tid]),
            })
            logger.debug(
                "[PersonCluster] Track %d (%.1fs) registered as %s (best_sim=%.3f)",
                tid, t_dur, new_label, best_sim,
            )

    # 6. Global post-consolidation: Merge any clusters that share >= 0.72 appearance and no collision
    consolidated: List[Dict[str, Any]] = []
    to_skip = set()

    for i in range(len(clusters)):
        if i in to_skip:
            continue
        c1 = clusters[i]

        for j in range(i + 1, len(clusters)):
            if j in to_skip:
                continue
            c2 = clusters[j]

            # Check collision
            has_collision = False
            for s1, e1 in c1["intervals"]:
                for s2, e2 in c2["intervals"]:
                    if min(e1, e2) - max(s1, s2) > temporal_collision_ms:
                        has_collision = True
                        break
                if has_collision:
                    break

            if has_collision:
                continue

            # Compare appearance
            if c1["embedding"] is not None and c2["embedding"] is not None:
                sim = float(np.dot(c1["embedding"], c2["embedding"]))
                if sim >= 0.72:
                    # Merge c2 into c1
                    n1 = len(c1["track_ids"])
                    n2 = len(c2["track_ids"])
                    c1["embedding"] = (c1["embedding"] * n1 + c2["embedding"] * n2) / (n1 + n2)
                    c1["embedding"] /= (np.linalg.norm(c1["embedding"]) + 1e-8)
                    c1["track_ids"].extend(c2["track_ids"])
                    c1["intervals"].extend(c2["intervals"])
                    c1["clips"].extend(c2["clips"])
                    if not c1["best_crop_path"]:
                        c1["best_crop_path"] = c2["best_crop_path"]
                    to_skip.add(j)
                    logger.debug("[PersonCluster] Consolidated %s into %s (sim=%.3f)", c2["label"], c1["label"], sim)

        consolidated.append(c1)

    # 7. Renumber cleanly to "Person 1", "Person 2", ... ordered by total active duration
    consolidated.sort(
        key=lambda c: sum(e - s for s, e in c["intervals"]),
        reverse=True,
    )

    final_track_to_person: Dict[int, str] = {}
    final_gallery: Dict[str, Dict[str, Any]] = {}

    for idx, c in enumerate(consolidated, start=1):
        person_lbl = f"Person {idx}"
        first_ms = min(s for s, _ in c["intervals"])
        last_ms = max(e for _, e in c["intervals"])
        total_active_s = sum(e - s for s, e in c["intervals"]) / 1000.0

        for tid in c["track_ids"]:
            final_track_to_person[tid] = person_lbl

        # Find top activity for clean factual description
        act_counts = Counter(clip.get("event_type") for clip in c["clips"])
        top_act = act_counts.most_common(1)[0][0] if act_counts else "active"
        top_act_clean = top_act.replace("person_", "").replace("_", " ")

        final_gallery[person_lbl] = {
            "person_label": person_lbl,
            "description": f"Tracked subject ({top_act_clean}, active {total_active_s:.1f}s)",
            "first_seen_ms": first_ms,
            "last_seen_ms": last_ms,
            "observation_count": len(c["clips"]) * 5,
            "entry_direction": "scene",
            "track_ids": sorted(c["track_ids"]),
            "best_crop_path": c["best_crop_path"],
        }

    return final_track_to_person, final_gallery
