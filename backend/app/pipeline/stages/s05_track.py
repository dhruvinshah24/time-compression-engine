"""
Pipeline Stage s05: Multi-Object Tracking + ReID + Activity Classification — Phase 7.

Three passes in sequence:
  Pass 1 — IoU-based Multi-Object Tracking (unchanged from Phase 4).
            Assigns monotonically increasing track IDs.
            Output: Track objects with full observation history.

  Pass 2 — Person Re-Identification (ReID).
            For every confirmed person track:
              a. Loads the frame image for the track's best observation.
              b. Extracts person crop.
              c. Computes appearance embedding (GPU: MobileNetV3, CPU: HSV histogram).
              d. Matches against PersonGallery → assigns "Person 1", "Person 2" labels.
              e. Saves JPEG crop for frontend thumbnails.
            Output: track.person_label set on all person Track objects.

  Pass 3 — Activity Classification.
            For every confirmed person track:
              Analyses velocity profile, vertical drift, nearby objects →
              dominant activity label + confidence + evidence.
            Output: track.activity (stored in context metadata per track).

Success criteria (Phase 7):
  - Every confirmed person track gets a "Person N" label.
  - Crops saved to outputs/{job_id}/crops/.
  - Activity labels available for s07 narrative event generation.
  - Zero crashes if ReID dependencies (torch, cv2) are unavailable.
"""

import logging
import time
from pathlib import Path

from app.engines.perception.tracker.config import TrackerConfig
from app.engines.perception.tracker.tracker import MultiObjectTracker, TrackingResult
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s05_track"

# Person class names — must match YOLO-World vocabulary
PERSON_CLASSES = {"person", "man", "woman", "child", "baby"}


async def run(context: PipelineContext) -> StageResult:
    """
    Run multi-object tracking, person ReID, and activity classification.

    Reads from context:
        metadata["frame_detections"]    — list of FrameDetectionResult (from s04)
        metadata["fps"]                 — video FPS
        metadata["frame_paths"]         — {frame_number: absolute_path} (from s04)

    Writes to context:
        metadata["tracking_result"]     — TrackingResult
        metadata["all_tracks"]          — list of all Track objects
        metadata["active_tracks"]       — tracks still active at end
        metadata["ended_tracks"]        — tracks that were closed
        metadata["total_tracks"]        — total count
        metadata["person_gallery"]      — PersonGallery dict (for s07)
        metadata["track_activities"]    — {track_id: ActivityResult} (for s07)
        metadata["track_to_label"]      — {track_id: "Person N"} (for s07)
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting multi-object tracking + ReID for job {context.job_id}")

    # ── Pass 1: Read frame detections ────────────────────────────────────────
    frame_detections = context.metadata.get("frame_detections")
    if frame_detections is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["frame_detections not in context — s04_object_detect must run first"],
            logs=logs,
        )

    total_input_detections = sum(r.detection_count for r in frame_detections)
    logs.append(
        f"[{STAGE_NAME}] Processing {len(frame_detections)} frames, "
        f"{total_input_detections} total detections"
    )

    # ── Pass 1: IoU Tracking ─────────────────────────────────────────────────
    try:
        from scipy.optimize import linear_sum_assignment  # noqa: F401
    except ImportError:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["scipy not installed. Run: pip install scipy"],
            logs=logs,
        )

    config = TrackerConfig(
        iou_threshold=float(context.settings.get(
            "tracker_iou_threshold", 0.25)),
        max_lost_frames=int(context.settings.get(
            "tracker_max_lost",          # key set by upload.py
            context.settings.get("tracker_max_lost_frames", 15))),
        min_confirmation_frames=int(context.settings.get(
            "tracker_min_confirm",
            context.settings.get("tracker_min_confirmation_frames", 2))),
        min_detection_confidence=float(
            context.settings.get("detection_confidence", 0.25)
        ),
    )
    logs.append(
        f"[{STAGE_NAME}] Tracker config: iou={config.iou_threshold}, "
        f"max_lost={config.max_lost_frames}, confirm={config.min_confirmation_frames}"
    )

    tracker = MultiObjectTracker(config=config)
    sorted_frames = sorted(frame_detections, key=lambda r: r.frame_number)
    for frame_result in sorted_frames:
        tracker.update(frame_result)
    result: TrackingResult = tracker.finalize()

    # Per-class occlusion tolerance override (person gets extra tolerance)
    _FURNITURE = {
        "chair", "office_chair", "sofa", "couch", "bed", "desk", "table",
        "dining_table", "shelf", "bookshelf", "cabinet", "wardrobe", "bench",
        "stool", "curtain",
    }
    for track in result.all_tracks:
        cn = (track.class_name or "").lower()
        if cn in PERSON_CLASSES:
            if hasattr(track, "max_lost_frames"):
                track.max_lost_frames = 20   # ~2s at skip=3, fps=30
        elif cn in _FURNITURE:
            if hasattr(track, "max_lost_frames"):
                track.max_lost_frames = 4

    logs.append(
        f"[{STAGE_NAME}] Pass 1 complete: {result.total_tracks_created} tracks created, "
        f"{len(result.confirmed_tracks)} confirmed"
    )

    # ── Pass 2: ReID ─────────────────────────────────────────────────────────
    track_to_label: dict[int, str] = {}
    gallery_dict: dict = {}

    try:
        from app.utils.person_reid import AppearanceEmbedder, PersonGallery
        from app.utils.crop_extractor import extract_and_save_crops

        # Build frame_number → path mapping from s04 output
        frame_paths: dict[int, str] = context.metadata.get("frame_paths", {})

        # If frame_paths not populated by s04, try to reconstruct from frame_detections
        if not frame_paths:
            for fdr in frame_detections:
                if hasattr(fdr, "frame_path") and fdr.frame_path:
                    frame_paths[fdr.frame_number] = fdr.frame_path
            logs.append(
                f"[{STAGE_NAME}] frame_paths reconstructed from frame_detections: "
                f"{len(frame_paths)} paths"
            )

        embedder = AppearanceEmbedder()
        logs.append(f"[{STAGE_NAME}] ReID mode: {embedder.mode}")

        gallery = PersonGallery(
            embedder=embedder,
            similarity_threshold=float(
                context.settings.get("reid_similarity_threshold",
                                     0.52)   # matches SIMILARITY_THRESHOLD in person_reid.py
            ),
        )

        output_dir = str(Path(context.output_dir))
        track_to_label = extract_and_save_crops(
            frame_paths=frame_paths,
            all_tracks=result.all_tracks,
            output_dir=output_dir,
            embedder=embedder,
            gallery=gallery,
        )

        gallery_dict = gallery.to_dict()
        n_persons = len(set(track_to_label.values()))
        logs.append(
            f"[{STAGE_NAME}] Pass 2 (ReID) complete: {n_persons} unique persons identified"
        )

        # List all identified persons
        for label in sorted(set(track_to_label.values())):
            entry = gallery_dict.get(label, {})
            logs.append(
                f"[{STAGE_NAME}]   {label}: seen {entry.get('observation_count', 0)}x, "
                f"entry={entry.get('entry_direction', '?')}"
            )

    except Exception as exc:  # noqa: BLE001
        warnings.append(f"ReID pass failed (non-fatal): {exc}")
        logger.warning("[%s] ReID pass failed: %s", STAGE_NAME, exc, exc_info=True)
        # Fallback: assign sequential labels to person tracks
        pid = 1
        for track in result.all_tracks:
            if track.class_name.lower() in PERSON_CLASSES and track.is_confirmed:
                label = f"Person {pid}"
                track.person_label = label
                track_to_label[track.track_id] = label
                pid += 1

    # ── Pass 3: Activity Classification ─────────────────────────────────────
    track_activities: dict[int, object] = {}

    try:
        from app.utils.activity_classifier import ActivityClassifier

        fps = float(context.metadata.get("fps", 30.0))
        frame_skip = int(context.settings.get("frame_skip_rate", 5))
        clf = ActivityClassifier(fps=fps, frame_skip=frame_skip)

        confirmed_person_tracks = [
            t for t in result.all_tracks
            if t.class_name.lower() in PERSON_CLASSES and t.is_confirmed
        ]

        for track in confirmed_person_tracks:
            activity = clf.classify(track, all_tracks=result.all_tracks)
            track_activities[track.track_id] = activity
            label = track.person_label or f"Track-{track.track_id}"
            logs.append(
                f"[{STAGE_NAME}]   {label}: {activity.label} "
                f"(conf={activity.confidence:.2f}, dur={activity.duration_ms/1000:.1f}s)"
            )

        logs.append(
            f"[{STAGE_NAME}] Pass 3 (Activity) complete: "
            f"{len(track_activities)} tracks classified"
        )

    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Activity classification failed (non-fatal): {exc}")
        logger.warning("[%s] Activity pass failed: %s", STAGE_NAME, exc, exc_info=True)

    # ── Store in context ─────────────────────────────────────────────────────
    context.metadata["tracking_result"] = result
    context.metadata["all_tracks"]      = result.all_tracks
    context.metadata["active_tracks"]   = result.active_tracks
    context.metadata["ended_tracks"]    = result.ended_tracks
    context.metadata["total_tracks"]    = result.total_tracks_created
    context.metadata["person_gallery"]  = gallery_dict
    context.metadata["track_activities"] = track_activities
    context.metadata["track_to_label"]  = track_to_label

    # ── Warnings ─────────────────────────────────────────────────────────────
    if result.total_tracks_created == 0 and total_input_detections > 0:
        warnings.append(
            "Zero tracks created despite having detections. "
            "Check min_detection_confidence threshold."
        )
    elif result.total_tracks_created == 0:
        warnings.append("Zero tracks created — no detections from s04.")

    confirmed = result.confirmed_tracks
    if result.total_tracks_created > 0 and len(confirmed) == 0:
        warnings.append(
            "All tracks were tentative (never confirmed). "
            "Consider reducing min_confirmation_frames."
        )

    # ── Metrics ──────────────────────────────────────────────────────────────
    metrics = result.to_metrics_dict()
    metrics["total_input_detections"] = total_input_detections
    metrics["unique_persons_identified"] = len(set(track_to_label.values()))
    metrics["tracks_with_activity"] = len(track_activities)

    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] All passes complete in {duration_ms}ms: "
        f"{result.total_tracks_created} tracks, "
        f"{len(set(track_to_label.values()))} persons, "
        f"{len(track_activities)} activities"
    )

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics=metrics,
        artifacts=[],
        logs=logs,
    )
