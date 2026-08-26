"""
Pipeline Stage s07: Semantic Event Understanding — Phase 6 Implementation.

Answers "What happened?" rather than "What is visible?"

Three analysis passes, all merged into a single event list:

  Pass 1 — Rule-based track events (person_entered, person_walking, etc.)
            Uses confirmed tracks + motion profiles from s05/s06.

  Pass 2 — Brightness-based lighting events (light_turned_on/off)
            Analyzes mean pixel luminance of extracted frames.
            No ML model — pure signal processing.

  Pass 3 — Posture events (person_sitting, person_standing_up)
            Analyzes bbox aspect ratio changes over time.
            No ML model — pure geometry.

  Pass 4 — Object proximity events (person_near_chair, etc.)
            Detects when person track is near other detected object tracks.

All four passes produce Event objects with the same schema, so they flow
through s08–s12 identically. Every event has a full evidence dict.

Success criteria (Phase 6+):
  - Rule-based events for all confirmed tracks
  - Lighting events from brightness analysis
  - Sitting/standing posture events from bbox geometry
  - Zero events for empty video (not an error)
  - Evidence dict on every single event (explainability guarantee)
"""

import logging
import time
import uuid
from pathlib import Path

from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
from app.engines.semantic.event_understanding.engine import (
    Event,
    EventUnderstandingEngine,
    EventUnderstandingResult,
)
from app.engines.semantic.event_understanding.rules import EventType
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s07_event_understand"

# Loiter threshold (must match activity_classifier.py)
LOITER_STILL_SEC = 12.0


# ---------------------------------------------------------------------------
# Helpers: convert analysis results → Event objects
# ---------------------------------------------------------------------------

def _lighting_event_to_event(le) -> Event:
    """Convert a LightingEvent to a pipeline Event object."""
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=le.event_type,
        track_id=-1,           # scene-level event, no track
        class_name="scene",
        rule_name="brightness_analysis",
        confidence=le.confidence,
        evidence=le.evidence,
        start_frame=le.frame_number,
        end_frame=le.frame_number,
        start_ms=le.timestamp_ms,
        end_ms=le.timestamp_ms,
        dependencies=["brightness_analysis"],
    )


def _posture_event_to_event(pe) -> Event:
    """Convert a PostureEvent to a pipeline Event object."""
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=pe.event_type,
        track_id=pe.track_id,
        class_name="person",
        rule_name="posture_analysis",
        confidence=pe.confidence,
        evidence=pe.evidence,
        start_frame=pe.start_frame,
        end_frame=pe.end_frame,
        start_ms=pe.start_ms,
        end_ms=pe.end_ms,
        dependencies=[f"track_{pe.track_id}", "posture_analysis"],
    )


def _proximity_event_to_event(pe) -> Event:
    """Convert an ObjectProximityEvent to a pipeline Event object."""
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=pe.event_type,
        track_id=pe.track_id,
        class_name="person",
        rule_name="proximity_analysis",
        confidence=pe.confidence,
        evidence=pe.evidence,
        start_frame=pe.start_frame,
        end_frame=pe.end_frame,
        start_ms=pe.start_ms,
        end_ms=pe.end_ms,
        dependencies=[f"track_{pe.track_id}", "proximity_analysis"],
    )


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------

async def run(context: PipelineContext) -> StageResult:
    """
    Run all four event understanding passes and merge results.

    Reads from context:
        metadata["all_tracks"]            — Track list (from s05)
        metadata["motion_profiles"]       — dict[track_id, MotionProfile] (s06)
        metadata["camera_motion_frames"]  — list[int] (s06)
        metadata["frame_paths"]           — list[str] (s02) for brightness
        metadata["video_metadata"]        — for frame dimensions

    Writes to context:
        metadata["event_result"]    — EventUnderstandingResult
        metadata["events"]          — list[Event] (all passes merged)
        metadata["events_by_type"]  — dict[event_type, count]
        metadata["lighting_events"] — list[LightingEvent] (for s12/UI)
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting event understanding for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    all_tracks = context.metadata.get("all_tracks")
    if all_tracks is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False, stage_name=STAGE_NAME, duration_ms=duration_ms,
            errors=["all_tracks not in context — s05_track must run first"],
            logs=logs,
        )

    motion_profiles = context.metadata.get("motion_profiles", {})
    camera_motion_frames = context.metadata.get("camera_motion_frames", [])
    frame_paths_raw = context.metadata.get("frame_paths", [])

    # frame_paths may be a dict {frame_number: path} (from s04 v2) or
    # a plain list of path strings (from s02 directly). Normalize to list.
    if isinstance(frame_paths_raw, dict):
        # Sort by frame number so brightness analysis is temporally ordered
        frame_paths: list[str] = [
            str(v) for k, v in sorted(frame_paths_raw.items(), key=lambda x: int(x[0]))
        ]
    else:
        frame_paths = [str(p) for p in frame_paths_raw]

    # Get video dimensions from metadata
    video_meta = context.metadata.get("video_metadata")
    if hasattr(video_meta, "resolution_width"):
        frame_w = video_meta.resolution_width or 848
        frame_h = video_meta.resolution_height or 478
    elif isinstance(video_meta, dict):
        frame_w = video_meta.get("resolution_width", 848)
        frame_h = video_meta.get("resolution_height", 478)
    else:
        frame_w, frame_h = 848, 478

    fps = 30.0
    if hasattr(video_meta, "fps"):
        fps = video_meta.fps or 30.0
    elif isinstance(video_meta, dict):
        fps = video_meta.get("fps", 30.0)

    confirmed_tracks = [
        t for t in all_tracks
        if t.confirmed_at_frame is not None or t.is_confirmed
    ]
    # YOLO-World labels people as 'person', 'man', 'woman', 'child', 'baby'.
    # Expand the filter so ALL human detections feed the state machine.
    _HUMAN_CLASSES = {"person", "man", "woman", "child", "baby", "crowd"}
    person_tracks = [t for t in confirmed_tracks if (t.class_name or "").lower() in _HUMAN_CLASSES]

    logs.append(
        f"[{STAGE_NAME}] {len(all_tracks)} total tracks, "
        f"{len(confirmed_tracks)} confirmed, "
        f"{len(person_tracks)} person tracks"
    )

    all_events: list[Event] = []

    # ── Pass 1: Rule-based track events ────────────────────────────────────
    config = EventUnderstandingConfig(
        min_event_confidence=float(context.settings.get("event_min_confidence", 0.35)),
        min_track_frames_for_entry=int(context.settings.get("event_min_track_frames", 1)),
        suppress_camera_motion_events=bool(
            context.settings.get("event_suppress_camera_motion", True)
        ),
    )
    engine = EventUnderstandingEngine(config=config)
    result = engine.understand(
        tracks=all_tracks,
        motion_profiles=motion_profiles,
        camera_motion_frames=camera_motion_frames,
    )
    all_events.extend(result.events)
    logs.append(
        f"[{STAGE_NAME}] Pass 1 (rules):    {len(result.events)} events "
        f"| types: {result.events_by_type()}"
    )

    # ── Pass 2: Brightness-based lighting events ────────────────────────────
    lighting_events_raw = []
    # BUG-FIX S07-1: Initialize here so Pass 3 can reference these even if
    # frame_paths is empty or Pass 2's try-block throws before populating them.
    frame_numbers: list[int] = []
    timestamps_ms: list[float] = []
    if frame_paths:
        try:
            from app.utils.brightness import analyze_frames, detect_lighting_events

            # Build frame number + timestamp arrays from paths
            # Frame filenames: frame_XXXXXXXX.jpg
            # Timestamp = frame_number / fps * 1000
            frame_numbers: list[int] = []
            timestamps_ms: list[float] = []
            for p in frame_paths:
                stem = Path(p).stem  # e.g. "frame_00000375"
                parts = stem.split("_")
                try:
                    fn = int(parts[-1])
                except (ValueError, IndexError):
                    fn = len(frame_numbers)
                frame_numbers.append(fn)
                timestamps_ms.append(fn / fps * 1000.0)

            logs.append(
                f"[{STAGE_NAME}] Pass 2 (brightness): analyzing "
                f"{len(frame_paths)} frames..."
            )
            # Real indoor ceiling light switch: 10-20 luma unit change, sustained ≥2 frames.
            # Threshold 12.0 catches this reliably. Camera auto-exposure fluctuations
            # are usually <8 luma units and single-frame — filtered by min_consecutive=2.
            brightness_threshold = float(
                context.settings.get("brightness_threshold", 12.0)
            )
            frame_brightnesses = analyze_frames(
                frame_paths, frame_numbers, timestamps_ms
            )
            lighting_events_raw = detect_lighting_events(
                frame_brightnesses,
                brightness_threshold=brightness_threshold,
                merge_gap_ms=2000.0,    # merge events within 2s
                min_consecutive=2,       # 2 frames = ~0.2s at 10fps — real switch
            )

            context.metadata["lighting_events"] = lighting_events_raw
            context.metadata["frame_brightnesses"] = frame_brightnesses

            for le in lighting_events_raw:
                all_events.append(_lighting_event_to_event(le))

            logs.append(
                f"[{STAGE_NAME}] Pass 2 (brightness): "
                f"{len(lighting_events_raw)} lighting events detected"
                + (f" | threshold={brightness_threshold}" if lighting_events_raw else "")
            )
            if not lighting_events_raw:
                logs.append(
                    f"[{STAGE_NAME}] Pass 2: No lighting transitions detected "
                    f"(threshold={brightness_threshold}). "
                    "Room may have constant lighting or video is too dark."
                )
        except Exception as exc:
            logs.append(f"[{STAGE_NAME}] Pass 2 (brightness) skipped: {exc}")
            warnings.append(f"Brightness analysis failed: {exc}")
    else:
        logs.append(f"[{STAGE_NAME}] Pass 2 (brightness): no frame_paths in context — skipped")

    # ── Pass 3: Pose Estimation (YOLOv8-Pose keypoints) ────────────────────
    # This replaces bbox aspect ratio heuristics with actual body keypoints.
    # Detects: sitting, standing, walking, reaching_up (light switch gesture)
    pose_events_total = 0
    if frame_paths and person_tracks:
        try:
            from app.utils.pose_estimate import analyze_pose_frames, extract_pose_events

            logs.append(
                f"[{STAGE_NAME}] Pass 3 (pose): running YOLOv8-pose on "
                f"{len(frame_paths)} frames..."
            )
            pose_confidence = float(context.settings.get("pose_confidence", 0.20))

            frame_poses = analyze_pose_frames(
                frame_paths=frame_paths,
                frame_numbers=frame_numbers,
                timestamps_ms=timestamps_ms,
                model_name=context.settings.get("pose_model", "yolov8n-pose"),
                confidence=pose_confidence,
            )

            context.metadata["frame_poses"] = frame_poses

            if frame_poses:
                # Extract events from pose sequence
                # Use track_id=-1 (scene-level) since pose doesn't track IDs
                pose_events = extract_pose_events(
                    frame_poses=frame_poses,
                    track_id=person_tracks[0].track_id if person_tracks else -1,
                    min_consecutive_frames=int(
                        context.settings.get("pose_min_consecutive", 2)
                    ),
                    fps=fps,
                )
                for pe in pose_events:
                    all_events.append(Event(
                        event_id=str(uuid.uuid4()),
                        event_type=pe.event_type,
                        track_id=pe.track_id,
                        class_name="person",
                        rule_name="pose_estimation",
                        confidence=pe.confidence,
                        evidence=pe.evidence,
                        start_frame=pe.start_frame,
                        end_frame=pe.end_frame,
                        start_ms=pe.start_ms,
                        end_ms=pe.end_ms,
                        dependencies=["pose_keypoints"],
                    ))
                    pose_events_total += 1

            logs.append(
                f"[{STAGE_NAME}] Pass 3 (pose): {len(frame_poses)} poses analyzed, "
                f"{pose_events_total} events "
                f"| types: {set(pe.event_type for pe in pose_events) if frame_poses else set()}"
            )

        except Exception as exc:
            import traceback
            logs.append(f"[{STAGE_NAME}] Pass 3 (pose) failed: {exc}")
            logs.append(traceback.format_exc()[:500])
            warnings.append(f"Pose analysis failed: {exc}")

            # Fallback: bbox aspect ratio posture detection
            logs.append(f"[{STAGE_NAME}] Pass 3 fallback: bbox aspect ratio posture")
            try:
                from app.utils.posture import analyze_posture
                for track in person_tracks:
                    posture_events = analyze_posture(
                        track, frame_width=frame_w, frame_height=frame_h,
                        sitting_aspect_ratio_drop=0.55,
                        min_standing_aspect_ratio=1.40,
                        min_observations=3,
                    )
                    for pe in posture_events:
                        all_events.append(_posture_event_to_event(pe))
                    pose_events_total += len(posture_events)
            except Exception:
                pass

    # ── Pass 3b: Temporal Pose State Machine (bbox-based) ──────────────────
    # Uses TemporalPoseAnalyzer to detect SUSTAINED activities:
    # crawling, crouching, falling, running — from bounding box geometry.
    #
    # This pass runs on EVERY confirmed person track regardless of whether
    # yolo-pose was successful. It uses bbox geometry only (no keypoints).
    # Hysteresis gating: requires multiple consecutive frames before emitting.
    #
    # Status: IMPLEMENTED as of Phase 3. Phase 4: wired and run on real pipeline.
    # Results will be classified PARTIALLY VALIDATED after first real run.
    temporal_pose_events_total = 0
    if confirmed_tracks:
        try:
            from app.utils.pose_temporal import SimplePoseFrame, TemporalPoseAnalyzer

            temporal_pose_events: list = []
            for track in confirmed_tracks:
                if (track.class_name or "").lower() not in {
                    "person", "man", "woman", "child"
                }:
                    continue
                if len(track.observations) < 3:
                    continue

                analyzer = TemporalPoseAnalyzer(
                    track_id=track.track_id,
                    window_size=20,
                    min_frames_crawling=int(context.settings.get("pose_min_consecutive", 3)),
                    min_frames_crouching=int(context.settings.get("pose_min_consecutive", 3)),
                    min_frames_running=3,
                    min_frames_fallen=2,
                    hysteresis_frames=2,
                )

                for obs in track.observations:
                    bbox = getattr(obs, "bbox", None)
                    if bbox is None or len(bbox) < 4:
                        continue
                    x1, y1, x2, y2 = bbox
                    # Normalise if pixel coords
                    if any(v > 1.5 for v in [x1, y1, x2, y2]):
                        x1 /= max(frame_w, 1)
                        y1 /= max(frame_h, 1)
                        x2 /= max(frame_w, 1)
                        y2 /= max(frame_h, 1)

                    spf = SimplePoseFrame.from_bbox(
                        frame_number=obs.frame_number,
                        timestamp_ms=obs.timestamp_ms,
                        track_id=track.track_id,
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        frame_h=1.0,  # already normalised above
                    )
                    spf.pose_confidence = float(getattr(obs, "confidence", 0.5))
                    evt = analyzer.update(spf)
                    if evt:
                        temporal_pose_events.append(evt)

                # Flush pending events at track end
                temporal_pose_events.extend(analyzer.flush())

            for tpe in temporal_pose_events:
                d = tpe.to_pipeline_event_dict()
                all_events.append(Event(
                    event_id=str(uuid.uuid4()),
                    event_type=d["event_type"],
                    track_id=d["track_id"],
                    class_name="person",
                    rule_name="temporal_pose_bbox",
                    confidence=d["confidence"],
                    evidence={
                        **d["evidence"],
                        "source": "TemporalPoseAnalyzer",
                        "note": (
                            "IMPLEMENTED — thresholds not yet calibrated against "
                            "real labelled footage. Treat events as candidate observations."
                        ),
                    },
                    start_frame=d["start_frame"],
                    end_frame=d["end_frame"],
                    start_ms=d["start_ms"],
                    end_ms=d["end_ms"],
                    dependencies=[f"track_{d['track_id']}", "temporal_pose"],
                ))
                temporal_pose_events_total += 1

            logs.append(
                f"[{STAGE_NAME}] Pass 3b (temporal_pose_bbox): "
                f"{temporal_pose_events_total} sustained-activity events "
                f"from {len(confirmed_tracks)} track(s)"
            )

        except Exception as exc:
            import traceback
            logs.append(f"[{STAGE_NAME}] Pass 3b (temporal_pose_bbox) failed (non-fatal): {exc}")
            logs.append(traceback.format_exc()[:400])
            warnings.append(f"Temporal pose analysis failed: {exc}")

    # ── Pass 5: Activity State Machine (REPLACES noisy frame-by-frame events) ─
    # The state machine analyses the full person track trajectory and emits
    # one event per state transition — no duplicate "reaching_up" or
    # repeated "person_walking" every 2 frames.
    #
    # Strategy: run state machine for each person track, then REPLACE the
    # rule-based person events (Pass 1) with state-machine events for that track.
    # Non-person events (lighting) are kept as-is.

    sm_events_total = 0
    sm_replaced_track_ids: set[int] = set()

    if person_tracks and confirmed_tracks:
        frame_poses = context.metadata.get("frame_poses", [])
        try:
            from app.utils.activity_state_machine import run_activity_state_machine

            for track in person_tracks:
                if len(track.observations) < 2:
                    continue
                sm_evts = run_activity_state_machine(
                    person_track=track,
                    all_tracks=confirmed_tracks,
                    frame_poses=frame_poses,
                    fps=fps,
                )
                for ae in sm_evts:
                    all_events.append(Event(
                        event_id=str(uuid.uuid4()),
                        event_type=ae.event_type,
                        track_id=ae.track_id,
                        class_name="person",
                        rule_name="activity_state_machine",
                        confidence=ae.confidence,
                        evidence=ae.evidence,
                        start_frame=ae.start_frame,
                        end_frame=ae.end_frame,
                        start_ms=ae.start_ms,
                        end_ms=ae.end_ms,
                        dependencies=[f"track_{ae.track_id}", "state_machine"],
                    ))
                sm_events_total += len(sm_evts)
                sm_replaced_track_ids.add(track.track_id)

            logs.append(
                f"[{STAGE_NAME}] Pass 5 (state_machine): {sm_events_total} transition events "
                f"from {len(sm_replaced_track_ids)} person track(s)"
            )

            # Remove duplicate person events from Pass 1 for tracks now
            # handled by the state machine (avoid double "person_entered" etc.)
            PERSON_EVENT_TYPES = {
                EventType.PERSON_ENTERED_SCENE, EventType.PERSON_LEFT_SCENE,
                EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
                EventType.PERSON_STANDING, EventType.PERSON_LOITERING,
                EventType.PERSON_SITTING, EventType.PERSON_STANDING_UP,
            }
            all_events = [
                e for e in all_events
                if not (
                    e.event_type in PERSON_EVENT_TYPES
                    and e.track_id in sm_replaced_track_ids
                    and e.rule_name != "activity_state_machine"
                )
            ]
            logs.append(
                f"[{STAGE_NAME}] Pass 5: removed duplicate Pass 1/3 person events "
                f"for state-machine tracks"
            )

        except Exception as exc:
            import traceback
            logs.append(f"[{STAGE_NAME}] Pass 5 (state_machine) failed: {exc}")
            logs.append(traceback.format_exc()[:600])
            warnings.append(f"State machine failed: {exc}")

    # ── Pass 6: Person-Object Interaction Detection ────────────────────────
    # Detects high-level interactions: person picking up phone, drinking,
    # reading, using laptop, pocketing objects, watching screen.
    # Uses spatial proximity + temporal co-occurrence on YOLO-World tracks.
    interaction_events_total = 0
    if person_tracks:
        try:
            from app.utils.interaction_detector import InteractionDetector
            frame_skip = int(context.settings.get("frame_skip_rate", 5))
            detector = InteractionDetector(fps=fps, frame_skip=frame_skip)
            raw_interactions = detector.detect(person_tracks, confirmed_tracks)
            for ie in raw_interactions:
                all_events.append(Event(
                    event_id=ie.event_id,
                    event_type=ie.event_type,
                    track_id=ie.track_id,
                    class_name="person",
                    rule_name="interaction_detector",
                    confidence=ie.confidence,
                    evidence=ie.evidence,
                    start_frame=ie.start_frame,
                    end_frame=ie.end_frame,
                    start_ms=ie.start_ms,
                    end_ms=ie.end_ms,
                    dependencies=[f"track_{ie.track_id}", f"obj_track_{ie.object_track_id}"],
                ))
            interaction_events_total = len(raw_interactions)
            if raw_interactions:
                types = {ie.event_type for ie in raw_interactions}
                logs.append(
                    f"[{STAGE_NAME}] Pass 6 (interactions): {interaction_events_total} events "
                    f"| types: {types}"
                )
            else:
                logs.append(f"[{STAGE_NAME}] Pass 6 (interactions): 0 interactions detected")
        except Exception as exc:
            import traceback
            logs.append(f"[{STAGE_NAME}] Pass 6 (interactions) failed: {exc}")
            logs.append(traceback.format_exc()[:400])

    # ── Pass 6b: Scene-level security events ──────────────────────────────
    # Detects: unattended_bag, group_gathering, person_fallen, person_carrying
    security_events_total = 0
    if confirmed_tracks:
        try:
            sec_detector = InteractionDetector(
                fps=fps,
                frame_skip=int(context.settings.get("frame_skip_rate", 3)),
            )
            scene_evts = sec_detector.detect_scene_events(
                all_tracks=confirmed_tracks,
                person_tracks=person_tracks,
                video_fps=fps,
            )
            for se in scene_evts:
                all_events.append(Event(
                    event_id=se.event_id,
                    event_type=se.event_type,
                    track_id=se.track_id,
                    class_name=se.object_class,
                    rule_name="security_detector",
                    confidence=se.confidence,
                    evidence=se.evidence,
                    start_frame=se.start_frame,
                    end_frame=se.end_frame,
                    start_ms=se.start_ms,
                    end_ms=se.end_ms,
                    dependencies=["security_detector"],
                ))
            security_events_total = len(scene_evts)
            if scene_evts:
                types = {e.event_type for e in scene_evts}
                logs.append(
                    f"[{STAGE_NAME}] Pass 6b (security): {security_events_total} events"
                    f" | types: {types}"
                )
            else:
                logs.append(f"[{STAGE_NAME}] Pass 6b (security): 0 security events")
        except Exception as exc:
            logs.append(f"[{STAGE_NAME}] Pass 6b (security) skipped: {exc}")


    # ── Suppress object_appeared / object_disappeared from final events ──────
    # These are low-signal noise for the user timeline. Interactions (Pass 6)
    # already capture the meaningful version ("person picked up bottle").
    # Object inventory panel still shows all detected objects.
    _SUPPRESS_TYPES = {EventType.OBJECT_APPEARED, EventType.OBJECT_DISAPPEARED}
    before_suppress = len(all_events)
    all_events = [e for e in all_events if e.event_type not in _SUPPRESS_TYPES]
    suppressed_count = before_suppress - len(all_events)
    if suppressed_count:
        logs.append(
            f"[{STAGE_NAME}] Suppressed {suppressed_count} object_appeared/disappeared events "
            "(shown in Objects panel, not in event log)"
        )

    # ── Deduplication: merge same-type events within 2.5s ──────────────────
    # This eliminates noise like 5× "person_reaching_up" in 5 seconds.
    try:
        from app.utils.activity_state_machine import deduplicate_and_merge
        pre_dedup = len(all_events)
        all_events = deduplicate_and_merge(all_events, merge_gap_ms=2500.0)
        logs.append(
            f"[{STAGE_NAME}] Dedup: {pre_dedup} → {len(all_events)} events "
            f"(merged {pre_dedup - len(all_events)} duplicates)"
        )
    except Exception as exc:
        logs.append(f"[{STAGE_NAME}] Dedup skipped: {exc}")

    # ── Pass 7: Narrative Enrichment + Person-Label Injection ────────────────
    # Uses ReID data from s05 to:
    #   a. Attach person_label to every person event ("Person 1").
    #   b. Inject entry/exit direction into ENTERED/LEFT events.
    #   c. Generate rich narrative events from ActivityClassifier results.
    #   d. Add crop_path to evidence for frontend thumbnails.
    try:
        track_to_label  = context.metadata.get("track_to_label", {})
        track_activities = context.metadata.get("track_activities", {})
        person_gallery  = context.metadata.get("person_gallery", {})

        # a. Attach person_label to all existing person events
        for evt in all_events:
            if evt.track_id in track_to_label:
                label = track_to_label[evt.track_id]
                evt.evidence["person_label"] = label
                gallery_entry = person_gallery.get(label, {})
                if gallery_entry.get("best_crop_path"):
                    evt.evidence["crop_path"] = gallery_entry["best_crop_path"]

        # b. Enrich ENTERED/LEFT events with direction info
        for evt in all_events:
            if evt.track_id in track_to_label:
                label = track_to_label[evt.track_id]
                gallery_entry = person_gallery.get(label, {})
                if evt.event_type == "person_entered_scene":
                    direction = gallery_entry.get("entry_direction") or evt.evidence.get("entry_dir")
                    if direction:
                        evt.evidence["direction"] = direction
                        evt.evidence["description"] = (
                            f"{label} entered the scene from the {direction}"
                        )
                elif evt.event_type == "person_left_scene":
                    direction = evt.evidence.get("exit_dir") or evt.evidence.get("at_edge")
                    if track_to_label.get(evt.track_id):
                        evt.evidence["description"] = (
                            f"{label} left the scene"
                            + (f" (via {direction} edge)" if isinstance(direction, str) else "")
                        )

        # c. Generate rich narrative activity events from ActivityClassifier
        activity_event_types = {
            "cycling", "running", "walking_upstairs", "walking_downstairs",
            "loitering", "walking",
        }
        narrative_events: list[Event] = []
        for track in person_tracks:
            activity = track_activities.get(track.track_id)
            if activity is None:
                continue

            label = track_to_label.get(track.track_id, f"Track-{track.track_id}")
            gallery_entry = person_gallery.get(label, {})
            crop_path = gallery_entry.get("best_crop_path")

            # Only generate narrative event if activity is interesting
            if activity.label not in activity_event_types:
                continue

            # Build human-readable description
            descriptions = {
                "cycling":            f"{label} is cycling across the scene",
                "running":            f"{label} is running",
                "walking_upstairs":   f"{label} is walking up stairs",
                "walking_downstairs": f"{label} is walking down stairs",
                "loitering":          f"{label} is loitering (stationary for >{LOITER_STILL_SEC:.0f}s)",
                "walking":            f"{label} is walking",
            }
            description = descriptions.get(activity.label, f"{label}: {activity.label}")

            if track.observations:
                first_obs = track.observations[0]
                narrative_events.append(Event(
                    event_id=str(uuid.uuid4()),
                    event_type=activity.label,
                    track_id=track.track_id,
                    class_name="person",
                    rule_name="narrative_builder",
                    confidence=activity.confidence,
                    evidence={
                        "person_label": label,
                        "description": description,
                        "crop_path": crop_path,
                        "entry_direction": activity.entry_direction,
                        "exit_direction": activity.exit_direction,
                        "duration_s": round((track.observations[-1].timestamp_ms - first_obs.timestamp_ms) / 1000, 1),
                        **activity.evidence,
                    },
                    start_frame=first_obs.frame_number,
                    end_frame=track.observations[-1].frame_number,
                    start_ms=first_obs.timestamp_ms,
                    end_ms=track.observations[-1].timestamp_ms,
                    dependencies=[f"track_{track.track_id}", "activity_classifier"],
                ))

        all_events.extend(narrative_events)
        logs.append(
            f"[{STAGE_NAME}] Pass 7 (narrative): {len(narrative_events)} rich activity events, "
            f"{len([e for e in all_events if 'person_label' in e.evidence])} person-labelled events"
        )

    except Exception as exc:
        import traceback
        logs.append(f"[{STAGE_NAME}] Pass 7 (narrative) failed (non-fatal): {exc}")
        logs.append(traceback.format_exc()[:400])
        warnings.append(f"Narrative enrichment failed: {exc}")

    # ── Pass 8: ROI / Virtual Zone Crossing ────────────────────────────────
    roi_events_total = 0
    try:
        roi_zones_cfg: list[dict] = context.settings.get("roi_zones", [])

        if roi_zones_cfg:
            from app.utils.roi_manager import ROIManager

            roi_mgr = ROIManager()
            roi_mgr.load_zones(roi_zones_cfg)

            for track in confirmed_tracks:
                if not track.observations:
                    continue
                if (track.class_name or "").lower() not in {
                    "person", "man", "woman", "child", "baby", "crowd"
                }:
                    continue

                track_label = context.metadata.get("track_to_label", {}).get(
                    track.track_id, f"Track-{track.track_id}"
                )
                motion_profile = motion_profiles.get(track.track_id)

                for obs in track.observations:
                    bbox = getattr(obs, "bbox", None)
                    if bbox is None or len(bbox) < 4:
                        continue

                    x1, y1, x2, y2 = bbox
                    if any(v > 1.5 for v in [x1, y1, x2, y2]):
                        x1 /= max(frame_w, 1)
                        y1 /= max(frame_h, 1)
                        x2 /= max(frame_w, 1)
                        y2 /= max(frame_h, 1)

                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    conf = getattr(obs, "confidence", 1.0)

                    zone_events = roi_mgr.check_point(
                        track_id=str(track.track_id),
                        cx=cx, cy=cy,
                        frame_number=obs.frame_number,
                        timestamp_ms=obs.timestamp_ms,
                        confidence=conf,
                    )

                    for ze in zone_events:
                        deps = [f"track_{track.track_id}", f"roi_{ze.zone_id}"]
                        if motion_profile:
                            deps.append(f"motion_profile_{track.track_id}")

                        evt = Event(
                            event_id=str(uuid.uuid4()),
                            event_type=ze.event_type,
                            track_id=track.track_id,
                            class_name="person",
                            rule_name=f"roi_{ze.zone_id}",
                            confidence=round(min(ze.confidence + 0.05, 1.0), 3),
                            evidence={
                                "person_label": track_label,
                                "zone_id": ze.zone_id,
                                "zone_name": ze.zone_name,
                                "zone_type": ze.zone_type.value,
                                "direction": ze.direction,
                                "centroid_x": ze.centroid_x,
                                "centroid_y": ze.centroid_y,
                                "track_confidence": conf,
                                "description": (
                                    f"{track_label} {ze.direction} "
                                    f"{ze.zone_name} at "
                                    f"{int(ze.timestamp_ms // 60000):02d}:"
                                    f"{int((ze.timestamp_ms % 60000) // 1000):02d}"
                                ),
                                **ze.evidence,
                            },
                            start_frame=ze.frame_number,
                            end_frame=ze.frame_number,
                            start_ms=ze.timestamp_ms,
                            end_ms=ze.timestamp_ms,
                            dependencies=deps,
                        )
                        all_events.append(evt)
                        roi_events_total += 1

            logs.append(
                f"[{STAGE_NAME}] Pass 8 (ROI): {roi_events_total} zone-crossing events "
                f"from {len(roi_zones_cfg)} zone(s)"
            )
        else:
            logs.append(f"[{STAGE_NAME}] Pass 8 (ROI): no zones configured — skipped")

    except Exception as exc:
        import traceback
        logs.append(f"[{STAGE_NAME}] Pass 8 (ROI) failed (non-fatal): {exc}")
        logs.append(traceback.format_exc()[:400])
        warnings.append(f"ROI zone analysis failed: {exc}")

    # ── Assemble final result ──────────────────────────────────────────────
    all_events.sort(key=lambda e: e.start_ms)

    merged_result = EventUnderstandingResult(
        events=all_events,
        total_events=len(all_events),
        tracks_analyzed=len(confirmed_tracks),
        rules_evaluated=result.rules_evaluated,
        camera_motion_frames_skipped=result.camera_motion_frames_skipped,
    )

    context.metadata["event_result"] = merged_result
    context.metadata["events"] = all_events
    context.metadata["events_by_type"] = merged_result.events_by_type()

    # ── Warnings ───────────────────────────────────────────────────────────
    if len(all_events) == 0 and len(confirmed_tracks) > 0:
        warnings.append(
            "Zero events generated despite confirmed tracks. "
            "Check event_min_confidence threshold or rule conditions."
        )
    if result.camera_motion_frames_skipped > 0:
        warnings.append(
            f"{result.camera_motion_frames_skipped} tracks suppressed "
            "due to camera motion overlap."
        )

    # ── Metrics ────────────────────────────────────────────────────────────
    metrics = merged_result.to_metrics_dict()
    metrics["lighting_events_detected"] = len(lighting_events_raw)
    metrics["pose_events_detected"] = pose_events_total
    metrics["temporal_pose_events"] = temporal_pose_events_total
    metrics["state_machine_events"] = sm_events_total
    metrics["state_machine_tracks"] = len(sm_replaced_track_ids)
    metrics["interaction_events"] = interaction_events_total
    metrics["security_events"] = security_events_total
    metrics["narrative_events"] = len(narrative_events) if 'narrative_events' in dir() else 0
    metrics["roi_events"] = roi_events_total
    metrics["unique_persons"] = len(set(context.metadata.get("track_to_label", {}).values()))
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Total: {len(all_events)} events "
        f"(rules={len(result.events)}, light={len(lighting_events_raw)}, "
        f"pose={pose_events_total}, temporal_pose={temporal_pose_events_total}, "
        f"state_machine={sm_events_total}, roi={roi_events_total})"
    )
    logs.append(f"[{STAGE_NAME}] Event types: {merged_result.events_by_type()}")
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

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
