"""
Phase 6 — Person Trace.

Selects one confirmed person from the RUN A result and traces them
through every stage: detection → track → motion → event → fusion →
story → rank → compression → export.

Writes:
  reports/person-trace-archive001-60s.json
"""
from __future__ import annotations
import asyncio, json, sys, tempfile, shutil, uuid, os
from pathlib import Path
import cv2

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT   = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"

GIT_COMMIT = "1ad97dd"
FROZEN_CONFIG = {
    "git_commit":          GIT_COMMIT,
    "model_profile":       "balanced",
    "detection_model":     "yolo11l",
    "pose_model":          "yolov8n-pose",
    "frame_skip_rate":     5,
    "detection_threshold": 0.25,
}

VIDEO = REPO_ROOT / "data/real/archive/videos/WhenYouA1948_512kb.mp4"
CLIP_S = 60


def extract_clip(src_path, duration_s, dst_path):
    cap = cv2.VideoCapture(src_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    n_to_write = min(int(fps * duration_s), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    out = cv2.VideoWriter(dst_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = 0
    while n < n_to_write:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame); n += 1
    cap.release(); out.release()
    return fps, w, h, n


def safe(v):
    if v is None or isinstance(v, (bool, int, float, str)): return v
    if isinstance(v, Path): return str(v)
    if isinstance(v, (list, tuple)): return [safe(x) for x in v]
    if isinstance(v, dict): return {str(k): safe(val) for k,val in v.items()}
    if isinstance(v, set): return sorted(safe(x) for x in v)
    if hasattr(v, '__dataclass_fields__'):
        return {k: safe(getattr(v, k)) for k in v.__dataclass_fields__}
    if hasattr(v, 'value'): return v.value
    try:
        import numpy as np
        if isinstance(v, np.integer): return int(v)
        if isinstance(v, np.floating): return float(v)
        if isinstance(v, np.ndarray): return v.tolist()
    except ImportError:
        pass
    return str(v)


async def run_and_trace():
    import logging
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)

    tmpdir = Path(tempfile.mkdtemp(prefix="tce_trace_"))
    os.environ["STORAGE_LOCAL_PATH"] = str(tmpdir / "outputs")

    try:
        print("[1] Extracting 60s clip...")
        clip_path = str(tmpdir / "clip.mp4")
        fps, w, h, nf = extract_clip(str(VIDEO), CLIP_S, clip_path)
        print("    %dx%d @ %.1f fps, %d frames" % (w, h, fps, nf))

        from app.pipeline.context import PipelineContext
        from app.repositories.inmemory import get_event_repo, get_job_repo
        from app.pipeline.orchestrator import PipelineOrchestrator

        job_id = "TRACE-%s" % uuid.uuid4().hex[:8].upper()
        context = PipelineContext(
            job_id    = job_id,
            video_id  = "VID-TRACE",
            video_path= clip_path,
            output_dir= str(tmpdir / "outputs"),
            settings  = {
                "model_profile":        FROZEN_CONFIG["model_profile"],
                "detection_model":      FROZEN_CONFIG["detection_model"],
                "detection_confidence": FROZEN_CONFIG["detection_threshold"],
                "frame_skip_rate":      FROZEN_CONFIG["frame_skip_rate"],
                "detection_threshold":  FROZEN_CONFIG["detection_threshold"],
                "low_light_enabled":    True,
                "pose_enabled":         True,
            },
        )

        print("[2] Running S01-S12...")
        orch = PipelineOrchestrator(get_job_repo(), get_event_repo())
        ok = await orch.run(context)
        print("    Pipeline ok=%s" % ok)

        md = context.metadata

        # ── Find best confirmed person track ──────────────────────────────
        all_tracks = md.get("all_tracks", [])
        person_tracks = [
            t for t in all_tracks
            if getattr(t, "class_name", "") in {"person","man","woman","child"}
            and getattr(t, "is_confirmed", False)
        ]
        if not person_tracks:
            # Fall back to highest-observation unconfirmed person track
            person_tracks = sorted(
                [t for t in all_tracks
                 if getattr(t, "class_name", "") in {"person","man","woman","child"}],
                key=lambda t: len(getattr(t, "observations", []) or []),
                reverse=True
            )[:1]

        if not person_tracks:
            print("ERROR: No person tracks found. Cannot trace.")
            return None

        target_track = person_tracks[0]
        track_id = getattr(target_track, "track_id", "?")
        print("[3] Target track: track_id=%s  is_confirmed=%s  observations=%d" % (
            track_id,
            getattr(target_track, "is_confirmed", "?"),
            len(getattr(target_track, "observations", []) or [])
        ))

        # ── Trace through each stage ───────────────────────────────────────
        trace = {
            "config": FROZEN_CONFIG,
            "target_track_id": track_id,
        }

        # Detection observations
        obs = getattr(target_track, "observations", []) or []
        det_sample = []
        for o in obs[:5]:
            det_sample.append({
                "frame":      getattr(o, "frame_number", "?"),
                "timestamp_s": round(getattr(o, "frame_number", 0) * 5 / fps, 2),
                "confidence": round(float(getattr(o, "confidence", 0)), 3),
                "bbox":       safe(getattr(o, "bbox", None)),
            })
        trace["detection"] = {
            "total_observations": len(obs),
            "first_frame":        getattr(obs[0], "frame_number", "?") if obs else "N/A",
            "last_frame":         getattr(obs[-1], "frame_number", "?") if obs else "N/A",
            "first_timestamp_s":  round(getattr(obs[0], "frame_number", 0) * 5 / fps, 2) if obs else "N/A",
            "last_timestamp_s":   round(getattr(obs[-1], "frame_number", 0) * 5 / fps, 2) if obs else "N/A",
            "sample_detections":  det_sample,
        }

        # Track state
        trace["track"] = {
            "track_id":     track_id,
            "class_name":   getattr(target_track, "class_name", "?"),
            "is_confirmed": getattr(target_track, "is_confirmed", "?"),
            "person_label": getattr(target_track, "person_label", "NOT ASSIGNED"),
            "activity":     safe(getattr(target_track, "activity", None)),
            "state":        safe(getattr(target_track, "state", None)),
            "age":          getattr(target_track, "age", "?"),
            "frames_tracked": len(obs),
            "continuity_note": "Track ID assigned by IoU tracker. ReID label assigned in S05.",
        }

        # Motion profile
        profiles = md.get("motion_profiles") or {}
        motion = profiles.get(track_id) or profiles.get(str(track_id))
        if motion is None:
            motion_snap = {"status": "NOT FOUND in motion_profiles — track may not have generated a profile"}
        else:
            motion_snap = safe(motion)
        trace["motion"] = motion_snap

        # Events for this track
        events = md.get("events", [])
        track_events = [
            e for e in events
            if (getattr(e, "track_id", None) == track_id
                or getattr(e, "track_id", None) == str(track_id))
        ]
        trace["semantic_events"] = [
            {
                "event_id":   getattr(e, "event_id", getattr(e, "id", "?")),
                "event_type": getattr(e, "event_type", "?"),
                "timestamp_s":safe(getattr(e, "timestamp", None)),
                "confidence": safe(getattr(e, "confidence", None)),
                "rule":       getattr(e, "rule", "?"),
                "evidence":   safe(getattr(e, "evidence", {})),
            }
            for e in track_events
        ]

        # Fused events for this track
        fused = md.get("fused_events", [])
        track_fused = [
            e for e in fused
            if (getattr(e, "track_id", None) == track_id
                or getattr(e, "track_id", None) == str(track_id))
        ]
        trace["fused_events"] = [
            {
                "event_id":       getattr(e, "event_id", getattr(e, "id", "?")),
                "event_type":     getattr(e, "event_type", "?"),
                "fused_confidence": safe(getattr(e, "fused_confidence", None)),
                "dimensions":     safe(getattr(e, "dimensions", {})),
                "fusion_strategy": safe(getattr(e, "fusion_strategy", None)),
            }
            for e in track_fused
        ]

        # Story segments containing this track
        segments = md.get("story_segments", [])
        track_segments = [
            s for s in segments
            if track_id in (getattr(s, "track_ids", []) or [])
            or str(track_id) in (getattr(s, "track_ids", []) or [])
        ]
        trace["story_segments"] = [
            {
                "segment_id":  safe(getattr(s, "segment_id", "?")),
                "completeness":safe(getattr(s, "completeness", None)),
                "importance":  safe(getattr(s, "importance_score", None)),
                "narrative":   safe(getattr(s, "narrative_score", None)),
                "event_count": len(getattr(s, "events", []) or []),
            }
            for s in track_segments
        ]

        # Ranking
        rr = md.get("ranking_result")
        ranked = getattr(rr, "ranked_segments", []) if rr else []
        track_ranked = [
            r for r in ranked
            if track_id in (getattr(r, "track_ids", []) or [])
            or str(track_id) in (getattr(r, "track_ids", []) or [])
        ]
        trace["ranking"] = [
            {
                "segment_id":   safe(getattr(r, "segment_id", "?")),
                "rank":         safe(getattr(r, "rank", None)),
                "combined_rank":safe(getattr(r, "combined_rank", None)),
                "importance":   safe(getattr(r, "importance_score", None)),
            }
            for r in track_ranked
        ]

        # Compression (S11 kept events)
        kept = md.get("summary_events", [])
        kept_ids = md.get("kept_event_ids", set())
        track_event_ids = {
            getattr(e, "event_id", getattr(e, "id", None))
            for e in track_events
        }
        track_kept = [
            e for e in kept
            if (getattr(e, "track_id", None) == track_id
                or getattr(e, "track_id", None) == str(track_id))
        ]
        trace["compression"] = {
            "track_event_ids":  list(track_event_ids),
            "kept_event_count": len(track_kept),
            "discard_count":    len(track_events) - len(track_kept),
            "decision":         "KEPT" if track_kept else "ALL DISCARDED",
        }

        # Export manifest
        em = md.get("export_manifest", {})
        exported = [
            ev for ev in (em.get("events", []) if isinstance(em, dict) else [])
            if ev.get("track_id") == track_id or ev.get("track_id") == str(track_id)
        ]
        trace["export"] = {
            "exported_event_count":  len(exported),
            "events":                exported[:5],
            "note": "0 exported events means S12 stored thumbnails but no clip manifest entries for this track.",
        }

        # Chain break analysis
        chain_breaks = []
        if len(obs) > 0 and len(track_events) == 0:
            chain_breaks.append("BREAK: Detection→Event — track had observations but no events (may be unconfirmed)")
        if len(track_events) > 0 and len(track_fused) == 0:
            chain_breaks.append("BREAK: Event→Fusion — events not in fused list")
        if len(track_fused) > 0 and len(track_segments) == 0:
            chain_breaks.append("BREAK: Fusion→Story — fused events not in any story segment")
        if len(track_segments) > 0 and len(track_kept) == 0:
            chain_breaks.append("BREAK: Story→Compression — all events discarded at S11")
        if len(track_kept) > 0 and len(exported) == 0:
            chain_breaks.append("BREAK: Compression→Export — kept events not in export manifest")
        if not chain_breaks:
            chain_breaks = ["No breaks detected in measured chain"]
        trace["chain_breaks"] = chain_breaks

        print("[4] Chain summary:")
        print("    Observations:     %d" % len(obs))
        print("    Semantic events:  %d" % len(track_events))
        print("    Fused events:     %d" % len(track_fused))
        print("    Story segments:   %d" % len(track_segments))
        print("    Kept events:      %d" % len(track_kept))
        print("    Exported:         %d" % len(exported))
        print("    Chain breaks:")
        for b in chain_breaks:
            print("      - %s" % b)

        # Write JSON
        out_path = REPORTS_DIR / "person-trace-archive001-60s.json"
        with open(out_path, "w") as fp:
            json.dump(safe(trace), fp, indent=2, default=str)
        print("[5] Saved: %s" % out_path)
        return trace

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_and_trace())
