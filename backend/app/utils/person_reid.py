"""
Person Re-Identification (ReID) Engine — Phase 7.

This module provides persistent person identity across video frames.
Instead of anonymous Track-42, people become "Person 1", "Person 2", etc.
Their identity survives occlusions and re-appearances.

Two-tier approach:
  Tier 1 (GPU): torchvision MobileNetV3-Small pretrained backbone.
                Extracts a 576-dim appearance embedding from a person crop.
                Cosine similarity for gallery matching.
                ~5ms per crop on GPU, ~25ms on CPU.

  Tier 2 (Fallback): HSV color histogram on 6 vertical body bands.
                     144-dim feature vector, no ML required.
                     Good enough for distinguishing 2-5 people in
                     controlled indoor-CCTV lighting.

Gallery matching algorithm:
  - For each new person track, compute appearance embedding.
  - Compare against all gallery entries using cosine similarity.
  - If best match > SIMILARITY_THRESHOLD → re-use that person label.
  - Otherwise → new person label ("Person N+1").
  - Update gallery entry with running mean of all embeddings seen.

Usage:
    embedder = AppearanceEmbedder()          # loads model once
    gallery  = PersonGallery(embedder)
    label    = gallery.match_or_register(crop_bgr, track_id=42)
    # → "Person 1"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70      # cosine sim threshold (0.70 distinguishes distinct actors reliably in CCTV while linking reappearing subjects)
MAX_GALLERY_AGE_MS   = 300_000   # remember person for 5 min of absence (was 2 min)
EMBEDDING_DIM_HIST   = 144       # 6 bands × 3 channels × 8 bins
EMBEDDING_DIM_DEEP   = 576       # MobileNetV3-Small last-pool features


# ── Appearance Embedder ────────────────────────────────────────────────────────

class AppearanceEmbedder:
    """
    Computes a compact appearance descriptor from a person crop (BGR numpy).

    Tries GPU-accelerated deep features first, falls back to color histograms.
    The output is always a 1-D float32 numpy array, L2-normalised.
    """

    def __init__(self) -> None:
        self._mode: str = "histogram"
        self._model = None
        self._transform = None
        self._device = None
        self._try_load_deep_model()

    def _try_load_deep_model(self) -> None:
        """Attempt to load MobileNetV3-Small from torchvision."""
        try:
            import torch
            import torchvision.models as tvm
            import torchvision.transforms as T

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            weights = tvm.MobileNet_V3_Small_Weights.DEFAULT
            backbone = tvm.mobilenet_v3_small(weights=weights)
            # Drop classifier → keep features only
            self._model = torch.nn.Sequential(*list(backbone.children())[:-1])
            self._model.to(device).eval()

            self._transform = T.Compose([
                T.ToPILImage(),
                T.Resize((128, 64)),     # person crop target size
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225]),
            ])
            self._device = device
            self._mode = "deep"
            logger.info(
                "[ReID] Deep appearance model loaded on %s (MobileNetV3-Small)",
                device,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[ReID] Deep model unavailable (%s) — using color histogram fallback",
                exc,
            )
            self._mode = "histogram"

    @property
    def mode(self) -> str:
        """Return 'deep' or 'histogram'."""
        return self._mode

    def compute(self, crop_bgr: np.ndarray) -> np.ndarray:
        """
        Compute and L2-normalise an appearance embedding.

        Args:
            crop_bgr: Person crop as (H, W, 3) BGR numpy array.

        Returns:
            1-D float32 numpy array, L2-normalised.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            dim = EMBEDDING_DIM_DEEP if self._mode == "deep" else EMBEDDING_DIM_HIST
            return np.zeros(dim, dtype=np.float32)

        # Ensure minimum size
        h, w = crop_bgr.shape[:2]
        if h < 16 or w < 8:
            # Too small to extract meaningful features
            dim = EMBEDDING_DIM_DEEP if self._mode == "deep" else EMBEDDING_DIM_HIST
            return np.zeros(dim, dtype=np.float32)

        if self._mode == "deep":
            return self._compute_deep(crop_bgr)
        return self._compute_histogram(crop_bgr)

    def _compute_deep(self, crop_bgr: np.ndarray) -> np.ndarray:
        """Extract MobileNetV3 features from crop."""
        import torch

        try:
            rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            tensor = self._transform(rgb).unsqueeze(0).to(self._device)
            with torch.no_grad():
                feat = self._model(tensor)
            vec = feat.squeeze().cpu().numpy().astype(np.float32)
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-8)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[ReID] Deep feature extraction failed: %s", exc)
            return self._compute_histogram(crop_bgr)

    def _compute_histogram(self, crop_bgr: np.ndarray) -> np.ndarray:
        """
        6-band HSV histogram ReID descriptor.

        Split person crop into 6 equal horizontal bands (head, upper torso,
        mid torso, hips, upper legs, lower legs). Compute 8-bin histograms
        for each H, S, V channel per band → 6×3×8 = 144 dimensions.

        Clothing changes horizontally → this captures outfit colour reliably
        in indoor CCTV where lighting is relatively stable.
        """
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        h, w = hsv.shape[:2]
        n_bands = 6
        band_h = max(1, h // n_bands)

        features: list[np.ndarray] = []
        for i in range(n_bands):
            band = hsv[i * band_h:(i + 1) * band_h, :]
            for ch, bins, rang in [
                (0, 8, (0, 180)),    # Hue
                (1, 8, (0, 256)),    # Saturation
                (2, 8, (0, 256)),    # Value
            ]:
                hist = cv2.calcHist([band], [ch], None, [bins], rang)
                hist = hist.flatten().astype(np.float32)
                s = hist.sum()
                features.append(hist / (s + 1e-8))

        vec = np.concatenate(features)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-8)


# ── Gallery Entry ──────────────────────────────────────────────────────────────

@dataclass
class GalleryEntry:
    """Stores all information known about one identified person."""
    person_label: str                            # "Person 1", "Person 2", …
    embedding: np.ndarray                        # running mean of all embeddings
    first_seen_ms: float = 0.0
    last_seen_ms:  float = 0.0
    observation_count: int = 0
    best_crop_path: Optional[str] = None        # absolute path to saved crop JPEG
    entry_direction: Optional[str] = None       # "left", "right", "top", "bottom"
    track_ids: list[int] = field(default_factory=list)  # all track IDs assigned
    intervals: list[tuple[float, float]] = field(default_factory=list)  # [(start_ms, end_ms)]


# ── Person Gallery ─────────────────────────────────────────────────────────────

class PersonGallery:
    """
    Maintains a gallery of known persons with persistent labels.

    Thread-safety: single-threaded within one pipeline run. No locks needed.
    """

    def __init__(
        self,
        embedder: AppearanceEmbedder,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ) -> None:
        self._embedder = embedder
        self._threshold = similarity_threshold
        self._entries: dict[str, GalleryEntry] = {}   # label → entry
        self._track_to_label: dict[int, str] = {}     # track_id → label
        self._next_id: int = 1

    # ── Public API ──────────────────────────────────────────────────────────

    def match_or_register(
        self,
        crop_bgr: np.ndarray,
        track_id: int,
        timestamp_ms: float = 0.0,
        entry_direction: Optional[str] = None,
        last_timestamp_ms: Optional[float] = None,
        observation_count: int = 1,
    ) -> str:
        """
        Find the best matching gallery person for a crop, or create a new one.

        Args:
            crop_bgr:          Person crop (BGR).
            track_id:          Track ID from the tracker.
            timestamp_ms:      When this was observed (ms from video start).
            entry_direction:   "left", "right", "top", "bottom" or None.
            last_timestamp_ms: Last seen timestamp (ms).
            observation_count: Total frames observed in this track.

        Returns:
            Person label string, e.g. "Person 1".
        """
        end_ts = last_timestamp_ms if last_timestamp_ms is not None else timestamp_ms
        add_obs = max(1, observation_count)

        # If track already has a label → just update timing
        if track_id in self._track_to_label:
            label = self._track_to_label[track_id]
            if label in self._entries:
                entry = self._entries[label]
                entry.first_seen_ms = min(entry.first_seen_ms, timestamp_ms)
                entry.last_seen_ms = max(entry.last_seen_ms, end_ts)
                entry.intervals.append((timestamp_ms, end_ts))
            return label

        embedding = self._embedder.compute(crop_bgr)

        # Try to match against gallery (excluding concurrent overlapping tracks)
        best_label, best_sim = self._find_best_match(
            embedding, track_interval=(timestamp_ms, end_ts)
        )

        if best_label is not None and best_sim >= self._threshold:
            label = best_label
            entry = self._entries[label]
            n = len(entry.track_ids)
            entry.embedding = (entry.embedding * n + embedding) / (n + 1)
            # Re-normalize to unit length so cosine similarity is preserved
            entry.embedding = entry.embedding / (np.linalg.norm(entry.embedding) + 1e-8)
            entry.first_seen_ms = min(entry.first_seen_ms, timestamp_ms)
            entry.last_seen_ms = max(entry.last_seen_ms, end_ts)
            entry.observation_count += add_obs
            entry.intervals.append((timestamp_ms, end_ts))
            if track_id not in entry.track_ids:
                entry.track_ids.append(track_id)
            logger.debug(
                "[ReID] Track %d re-identified as %s (cosine_sim=%.3f)",
                track_id, label, best_sim,
            )
        else:
            label = f"Person {self._next_id}"
            self._next_id += 1
            self._entries[label] = GalleryEntry(
                person_label=label,
                embedding=embedding,
                first_seen_ms=timestamp_ms,
                last_seen_ms=end_ts,
                observation_count=add_obs,
                entry_direction=entry_direction,
                track_ids=[track_id],
                intervals=[(timestamp_ms, end_ts)],
            )
            logger.info(
                "[ReID] New person registered: %s (track %d, sim=%.3f)",
                label, track_id, best_sim or 0.0,
            )

        self._track_to_label[track_id] = label
        return label

    def set_crop_path(self, person_label: str, crop_path: str) -> None:
        """Store the path to the best crop for a person."""
        if person_label in self._entries:
            self._entries[person_label].best_crop_path = crop_path

    def get_label(self, track_id: int) -> Optional[str]:
        """Look up an already-assigned person label."""
        return self._track_to_label.get(track_id)

    def all_entries(self) -> dict[str, GalleryEntry]:
        """Return the full gallery."""
        return dict(self._entries)

    def to_dict(self) -> dict:
        """Serialisable summary for pipeline metadata."""
        out = {}
        for label, entry in self._entries.items():
            out[label] = {
                "person_label": entry.person_label,
                "first_seen_ms": entry.first_seen_ms,
                "last_seen_ms": entry.last_seen_ms,
                "observation_count": entry.observation_count,
                "best_crop_path": entry.best_crop_path,
                "entry_direction": entry.entry_direction,
                "track_ids": entry.track_ids,
            }
        return out

    def consolidate_gallery(self, threshold: float = 0.72) -> int:
        """
        Merge gallery entries that represent the same person (cosine_sim >= threshold).
        Returns number of merges performed.
        """
        labels = list(self._entries.keys())
        merged_count = 0
        to_delete = set()

        for i in range(len(labels)):
            l1 = labels[i]
            if l1 in to_delete or l1 not in self._entries:
                continue
            e1 = self._entries[l1]

            for j in range(i + 1, len(labels)):
                l2 = labels[j]
                if l2 in to_delete or l2 not in self._entries:
                    continue
                e2 = self._entries[l2]

                # Physical reality check: do not merge tracks that were observed at the same time!
                has_temporal_overlap = False
                for s1, end1 in e1.intervals:
                    for s2, end2 in e2.intervals:
                        if min(end1, end2) - max(s1, s2) > 1000.0:
                            has_temporal_overlap = True
                            break
                    if has_temporal_overlap:
                        break

                if has_temporal_overlap:
                    continue

                sim = float(np.dot(e1.embedding, e2.embedding))
                if sim >= threshold:
                    # Merge e2 into e1
                    n1 = len(e1.track_ids)
                    n2 = len(e2.track_ids)
                    e1.embedding = (e1.embedding * n1 + e2.embedding * n2) / (n1 + n2)
                    e1.embedding = e1.embedding / (np.linalg.norm(e1.embedding) + 1e-8)
                    e1.first_seen_ms = min(e1.first_seen_ms, e2.first_seen_ms)
                    e1.last_seen_ms = max(e1.last_seen_ms, e2.last_seen_ms)
                    e1.observation_count += e2.observation_count
                    e1.intervals.extend(e2.intervals)
                    for tid in e2.track_ids:
                        if tid not in e1.track_ids:
                            e1.track_ids.append(tid)
                        self._track_to_label[tid] = l1
                    to_delete.add(l2)
                    merged_count += 1
                    logger.info("[ReID] Consolidated %s into %s (cosine_sim=%.3f)", l2, l1, sim)

        for l in to_delete:
            del self._entries[l]

        return merged_count

    # ── Internal ────────────────────────────────────────────────────────────

    def _find_best_match(
        self,
        embedding: np.ndarray,
        track_interval: Optional[tuple[float, float]] = None,
    ) -> tuple[Optional[str], float]:
        """Find gallery entry with highest cosine similarity, excluding entries with temporal collision."""
        if not self._entries:
            return None, 0.0

        best_label: Optional[str] = None
        best_sim: float = 0.0

        for label, entry in self._entries.items():
            # Physical reality check: two people observed simultaneously cannot be the same person!
            if track_interval is not None and entry.intervals:
                t_start, t_end = track_interval
                overlaps = False
                for s, e in entry.intervals:
                    if min(t_end, e) - max(t_start, s) > 1000.0:
                        overlaps = True
                        break
                if overlaps:
                    continue

            sim = float(np.dot(embedding, entry.embedding))  # both L2-normalised
            if sim > best_sim:
                best_sim = sim
                best_label = label

        return best_label, best_sim
