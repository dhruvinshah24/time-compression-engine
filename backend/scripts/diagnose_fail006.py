"""
Phase 6A — FAIL-006 Diagnostic.

Runs the PRODUCTION tracker on archive_001 60s and measures the
actual track lifetime distribution for all person tracks.

Determines whether min_confirmation_frames=2 is appropriate or
whether the real cause of low confirmation is something else.

Does NOT modify any code.
Writes: results/TCE-v1.0/fail006-diagnostic-archive001-60s.json
        reports/fail006-diagnostic-archive001-60s.md
"""
from __future__ import annotations
import asyncio, json, os, sys, shutil, tempfile, uuid
from pathlib import Path
from collections import defaultdict
import cv2

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT   = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
VIDEO = REPO_ROOT / "data/real/archive/videos/WhenYouA1948_512kb.mp4"
CLIP_S = 60


def extract_clip(src, dur, dst):
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    n = min(int(fps * dur), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    i = 0
    while i < n:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame); i += 1
    cap.release(); out.release()
    return fps


async def run_diagnostic():
    import logging
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)

    tmpdir = Path(tempfile.mkdtemp(prefix="tce_fail006_"))
    os.environ["STORAGE_LOCAL_PATH"] = str(tmpdir / "outputs")
    try:
        print("[1] Extracting 60s clip...")
        clip_path = str(tmpdir / "clip.mp4")
        fps = extract_clip(VIDEO, CLIP_S, clip_path)
        print("    fps=%.1f" % fps)

        from app.pipeline.context import PipelineContext
        from app.repositories.inmemory import get_event_repo, get_job_repo
        from app.pipeline.orchestrator import PipelineOrchestrator

        job_id = "DIAG-%s" % uuid.uuid4().hex[:6].upper()
        context = PipelineContext(
            job_id=job_id,
            video_id="VID-DIAG",
            video_path=clip_path,
            output_dir=str(tmpdir / "outputs"),
            settings={
                "model_profile":        "balanced",
                "detection_model":      "yolo11l",
                "detection_confidence": 0.25,
                "frame_skip_rate":      5,
                "detection_threshold":  0.25,
                "low_light_enabled":    True,
                "pose_enabled":         False,  # keep pose off; we are diagnosing tracking
            },
        )

        print("[2] Running S01-S05 (tracking only, pose disabled)...")
        from app.pipeline.stages import (
            s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track
        )
        import importlib
        for mod in [s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track]:
            r = await mod.run(context)
            print("    %s: ok=%s" % (mod.__name__.split(".")[-1], r.success))

        all_tracks = context.metadata.get("all_tracks", [])
        print("[3] Total tracks: %d" % len(all_tracks))

        # ── Categorise person tracks ───────────────────────────────────────
        PERSON_CLASSES = {"person", "man", "woman", "child", "baby"}
        person_tracks = [
            t for t in all_tracks
            if (t.class_name or "").lower() in PERSON_CLASSES
        ]

        # TrackerConfig values (current)
        from app.engines.perception.tracker.config import TrackerConfig
        cfg = TrackerConfig()
        MIN_CONF = cfg.min_confirmation_frames
        MIN_DET_CONF = cfg.min_detection_confidence
        MAX_LOST = cfg.max_lost_frames
        IOU_THRESH = cfg.iou_threshold

        print("[4] TrackerConfig:")
        print("    min_confirmation_frames = %d" % MIN_CONF)
        print("    min_detection_confidence = %.2f" % MIN_DET_CONF)
        print("    max_lost_frames = %d" % MAX_LOST)
        print("    iou_threshold = %.2f" % IOU_THRESH)

        # ── Per-track analysis ────────────────────────────────────────────
        from app.engines.perception.tracker.track import TrackState
        track_records = []
        for t in person_tracks:
            obs = t.observations or []
            obs_count = len(obs)
            confidences = [o.detection_confidence for o in obs]
            avg_conf = sum(confidences) / max(obs_count, 1)
            min_conf = min(confidences) if confidences else 0.0
            max_conf = max(confidences) if confidences else 0.0

            # Span in frames (distance from first to last frame seen)
            first_frame = obs[0].frame_number if obs else t.created_frame
            last_frame  = obs[-1].frame_number if obs else t.last_seen_frame
            frame_span  = last_frame - first_frame + 1

            # Why did it fail confirmation?
            is_confirmed = t.is_confirmed
            reason = "N/A"
            if is_confirmed:
                reason = "CONFIRMED"
            else:
                # Is it tentative still?
                if t.state == TrackState.TENTATIVE:
                    if obs_count < MIN_CONF:
                        reason = ("TENTATIVE_NEVER_CONFIRMED: only %d observations, "
                                  "need %d consecutive" % (obs_count, MIN_CONF))
                    else:
                        reason = ("TENTATIVE_ENOUGH_OBS_BUT_NOT_CONSECUTIVE: "
                                  "%d obs over %d frame span" % (obs_count, frame_span))
                elif t.state == TrackState.ENDED:
                    reason = "ENDED_BEFORE_CONFIRMATION"
                else:
                    reason = "STATE_%s" % t.state.value

            track_records.append({
                "track_id":       t.track_id,
                "class_name":     t.class_name,
                "state":          t.state.value,
                "is_confirmed":   is_confirmed,
                "obs_count":      obs_count,
                "frame_span":     frame_span,
                "duration_s":     round(frame_span * 5 / fps, 2),  # skip=5
                "avg_confidence": round(avg_conf, 3),
                "min_confidence": round(min_conf, 3),
                "max_confidence": round(max_conf, 3),
                "total_frames_matched": t.total_frames_matched,
                "reason": reason,
            })

        # ── Distribution of obs_count ─────────────────────────────────────
        bins = {"1":0, "2":0, "3-5":0, "6-10":0, "11-20":0, "21-49":0, "50+":0}
        for tr in track_records:
            n = tr["obs_count"]
            if n == 1:            bins["1"] += 1
            elif n == 2:          bins["2"] += 1
            elif n <= 5:          bins["3-5"] += 1
            elif n <= 10:         bins["6-10"] += 1
            elif n <= 20:         bins["11-20"] += 1
            elif n <= 49:         bins["21-49"] += 1
            else:                 bins["50+"] += 1

        # ── How many would confirm under alternate thresholds? ────────────
        alt_thresholds = {}
        for threshold in [1, 2, 3, 4, 5, 6, 8, 10]:
            would_confirm = sum(1 for tr in track_records if tr["obs_count"] >= threshold)
            alt_thresholds[threshold] = would_confirm

        # IMPORTANT: obs_count is TOTAL observations, but confirmation requires
        # CONSECUTIVE observations. Need to check consecutive matches.
        # The tracker counts total_frames_matched separately.
        consecutive_check = {}
        for threshold in [1, 2, 3, 4, 5]:
            would_confirm = sum(1 for tr in track_records if tr["total_frames_matched"] >= threshold)
            consecutive_check[threshold] = would_confirm

        # ── Summary ────────────────────────────────────────────────────────
        confirmed = [tr for tr in track_records if tr["is_confirmed"]]
        unconfirmed = [tr for tr in track_records if not tr["is_confirmed"]]

        # Reason breakdown
        reason_counts = defaultdict(int)
        for tr in unconfirmed:
            # Simplify reason key
            if "TENTATIVE_NEVER_CONFIRMED" in tr["reason"]:
                reason_counts["TENTATIVE_NEVER_CONFIRMED: insufficient observations"] += 1
            elif "TENTATIVE_ENOUGH_OBS_BUT_NOT_CONSECUTIVE" in tr["reason"]:
                reason_counts["TENTATIVE_ENOUGH_OBS_NOT_CONSECUTIVE"] += 1
            elif "ENDED_BEFORE_CONFIRMATION" in tr["reason"]:
                reason_counts["ENDED_BEFORE_CONFIRMATION"] += 1
            else:
                reason_counts[tr["reason"]] += 1

        print()
        print("=" * 60)
        print("FAIL-006 DIAGNOSTIC RESULTS")
        print("=" * 60)
        print()
        print("Person tracks:        %d total" % len(person_tracks))
        print("Confirmed:            %d" % len(confirmed))
        print("Unconfirmed:          %d" % len(unconfirmed))
        print()
        print("Current config:")
        print("  min_confirmation_frames  = %d" % MIN_CONF)
        print("  min_detection_confidence = %.2f" % MIN_DET_CONF)
        print()
        print("Observation count distribution:")
        for bucket, count in bins.items():
            pct = 100 * count / max(len(track_records), 1)
            bar = "#" * count
            print("  obs %6s: %2d tracks (%.0f%%) %s" % (bucket, count, pct, bar))
        print()
        print("total_frames_matched distribution (consecutive match count):")
        for threshold in sorted(consecutive_check):
            n = consecutive_check[threshold]
            print("  >= %2d frames_matched: %d tracks" % (threshold, n))
        print()
        print("Reason breakdown for unconfirmed tracks:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            print("  [%3d] %s" % (count, reason))
        print()
        print("Confidence distribution (all person tracks):")
        all_confs = [tr["avg_confidence"] for tr in track_records]
        brackets = {"<0.30":0, "0.30-0.40":0, "0.40-0.50":0, "0.50-0.65":0, ">=0.65":0}
        for c in all_confs:
            if c < 0.30:   brackets["<0.30"] += 1
            elif c < 0.40: brackets["0.30-0.40"] += 1
            elif c < 0.50: brackets["0.40-0.50"] += 1
            elif c < 0.65: brackets["0.50-0.65"] += 1
            else:           brackets[">=0.65"] += 1
        for b, n in brackets.items():
            print("  avg_conf %s: %d tracks" % (b, n))
        print()
        print("How many would confirm under alternate thresholds?")
        print("  (using obs_count as proxy — real confirmation requires consecutive)")
        for t, n in sorted(alt_thresholds.items()):
            note = " ← CURRENT" if t == MIN_CONF else ""
            print("  threshold=%d: %d/%d%s" % (t, n, len(track_records), note))
        print()
        print("Top 5 unconfirmed tracks by obs_count:")
        top_unc = sorted(unconfirmed, key=lambda x: -x["obs_count"])[:5]
        for tr in top_unc:
            print("  track_id=%-4d obs=%2d span=%d frames (%.1fs) avg_conf=%.3f reason=%s" % (
                tr["track_id"], tr["obs_count"], tr["frame_span"],
                tr["duration_s"], tr["avg_confidence"], tr["reason"][:60]
            ))

        # ── Save JSON ──────────────────────────────────────────────────────
        output = {
            "config": {
                "min_confirmation_frames": MIN_CONF,
                "min_detection_confidence": MIN_DET_CONF,
                "max_lost_frames": MAX_LOST,
                "iou_threshold": IOU_THRESH,
            },
            "summary": {
                "total_person_tracks": len(person_tracks),
                "confirmed": len(confirmed),
                "unconfirmed": len(unconfirmed),
                "confirmation_rate_pct": round(100 * len(confirmed) / max(len(person_tracks), 1), 1),
            },
            "obs_count_distribution": bins,
            "frames_matched_distribution": {str(k): v for k, v in consecutive_check.items()},
            "alt_threshold_comparison": {str(k): v for k, v in alt_thresholds.items()},
            "reason_counts": dict(reason_counts),
            "confidence_distribution": brackets,
            "track_records": track_records,
        }
        json_path = RESULTS_DIR / "fail006-diagnostic-archive001-60s.json"
        with open(json_path, "w") as f:
            json.dump(output, f, indent=2, default=str)

        # ── Write MD report ────────────────────────────────────────────────
        md_path = REPORTS_DIR / "fail006-diagnostic-archive001-60s.md"
        with open(md_path, "w", encoding="utf-8") as fp:
            fp.write("# FAIL-006 Diagnostic — archive_001 60s\n\n")
            fp.write("**FAIL-006:** Insufficient track confirmation on real footage.\n\n")
            fp.write("## TrackerConfig (current)\n\n")
            fp.write("| Parameter | Value |\n|---|---|\n")
            fp.write("| min_confirmation_frames | %d |\n" % MIN_CONF)
            fp.write("| min_detection_confidence | %.2f |\n" % MIN_DET_CONF)
            fp.write("| max_lost_frames | %d |\n" % MAX_LOST)
            fp.write("| iou_threshold | %.2f |\n\n" % IOU_THRESH)
            fp.write("## Summary\n\n")
            fp.write("| Metric | Value |\n|---|---|\n")
            fp.write("| Total person tracks | %d |\n" % len(person_tracks))
            fp.write("| Confirmed | %d |\n" % len(confirmed))
            fp.write("| Unconfirmed | %d |\n" % len(unconfirmed))
            fp.write("| Confirmation rate | %.1f%% |\n\n" % (100*len(confirmed)/max(len(person_tracks),1)))
            fp.write("## Observation Count Distribution\n\n")
            fp.write("| Bin | Count |\n|---|---|\n")
            for bucket, count in bins.items():
                fp.write("| %s obs | %d |\n" % (bucket, count))
            fp.write("\n## Reason Breakdown (unconfirmed)\n\n")
            for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
                fp.write("- **%d tracks**: %s\n" % (count, reason))
            fp.write("\n## Alternate Threshold Comparison\n\n")
            fp.write("| min_confirmation_frames | Tracks that would confirm |\n|---|---|\n")
            for t, n in sorted(alt_thresholds.items()):
                note = " ← CURRENT" if t == MIN_CONF else ""
                fp.write("| %d | %d/%d%s |\n" % (t, n, len(track_records), note))
        print()
        print("JSON: %s" % json_path)
        print("MD:   %s" % md_path)
        return output

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_diagnostic())
