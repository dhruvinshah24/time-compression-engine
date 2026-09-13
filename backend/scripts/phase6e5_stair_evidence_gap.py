"""
Phase 6E.5 — Stair Activity Capability & Evidence-Gap Diagnostic.

Extracts all confirmed person tracks (obs >= 5) from archive_001 (300s).
Correlates:
1. ActivityClassifier raw stair classifications (upstairs, downstairs)
2. TemporalPoseAnalyzer states (frame-by-frame candidate states, final state, state sequences)
3. Track kinematics (vx, vy, speed, aspect ratio, height variation)
4. Evaluates whether any existing signal or combination of signals can defensibly
   separate stair activity from perspective-induced motion.
"""
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from collections import Counter
import numpy as np

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
OUT_JSON = REPO / 'results/TCE-v1.0/phase6e5-stair-evidence-gap.json'

TARGET_TRACKS = [14, 56, 160, 177, 252, 273]


async def run():
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track,
    )
    from app.utils.activity_classifier import (
        ActivityClassifier,
        WALK_THRESHOLD,
        RUN_THRESHOLD,
        STAIR_VERT_THRESHOLD,
    )
    from app.utils.pose_temporal import (
        SimplePoseFrame,
        TemporalPoseAnalyzer,
        STATE_UNKNOWN,
        STATE_STANDING,
        STATE_WALKING,
        STATE_RUNNING,
        STATE_LOWERING,
        STATE_CROUCHING,
        STATE_CRAWLING,
        STATE_FALLEN,
        STATE_SITTING,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6e5_diag_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6E5-%s' % uuid.uuid4().hex[:6].upper()
    print(f'[SETUP] job_id={job_id}')

    clip_path = str(tmpdir / 'clip.mp4')
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    w, h = int(cap.get(3)), int(cap.get(4))
    n_frames = int(fps * 300)
    out = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    i = 0
    while i < n_frames:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame); i += 1
    cap.release(); out.release()

    ctx = PipelineContext(
        job_id=job_id, video_id='VID-6E5-DIAG', video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile': 'balanced', 'detection_model': 'yolo11l',
            'detection_confidence': 0.25, 'detection_threshold': 0.25,
            'frame_skip_rate': 5, 'low_light_enabled': True,
            'cycle_threshold': 0.25, 'require_temporal_overlap': True,
            'min_activity_observations': 5,
        },
    )

    for mod in [s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track]:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        print(f'  {name}: {"OK" if r.success else "FAIL"}')
        if not r.success:
            print(f'  ERRORS: {r.errors}'); return

    all_tracks = ctx.metadata.get('all_tracks', [])
    dt = 5 / max(fps, 1.0)

    _HUMAN_CLASSES = {"person", "man", "woman", "child", "baby", "crowd"}
    person_tracks = [
        t for t in all_tracks
        if (t.is_confirmed or t.confirmed_at_frame is not None)
        and (t.class_name or "").lower() in _HUMAN_CLASSES
        and len(t.observations) >= 5  # Phase 6E.2 guard
    ]
    print(f'\nTotal confirmed person tracks (obs >= 5): {len(person_tracks)}')

    clf = ActivityClassifier(
        fps=fps, frame_skip=5,
        cycle_threshold=0.25, require_temporal_overlap=True,
        min_activity_observations=5,
    )

    track_records = {}
    stair_positives = []

    for track in person_tracks:
        tid = track.track_id
        obs = track.observations
        n = len(obs)

        # 1. Activity Classifier result
        act_res = clf.classify(track, all_tracks=all_tracks)

        # Raw stair detection directly
        centers = []
        for o in obs:
            b = o.bbox
            if b is not None:
                from app.engines.perception.tracker.track import TrackBBox
                if isinstance(b, TrackBBox):
                    cx = (b.x1 + b.x2) / 2.0
                    cy = (b.y1 + b.y2) / 2.0
                elif hasattr(b, '__len__') and len(b) >= 4:
                    cx = (b[0] + b[2]) / 2.0
                    cy = (b[1] + b[3]) / 2.0
                else:
                    continue
                if any(v > 1.5 for v in [cx, cy]):
                    cx /= max(w, 1.0)
                    cy /= max(h, 1.0)
                centers.append((cx, cy))

        vy_arr = np.array([
            (centers[i][1] - centers[i-1][1]) / dt
            for i in range(1, len(centers))
        ]) if len(centers) >= 2 else np.array([])

        raw_stair_conf, raw_stair_dir = clf._detect_stairs(vy_arr, act_res.evidence.get('mean_speed', 0.0))
        mean_speed = act_res.evidence.get('mean_speed', 0.0)
        raw_stair_fires = (raw_stair_conf >= 0.55 and mean_speed >= WALK_THRESHOLD)

        # 2. Temporal Pose Analyzer
        tpa = TemporalPoseAnalyzer(
            track_id=tid,
            window_size=20,
            min_frames_crawling=3,
            min_frames_crouching=3,
            min_frames_running=3,
            min_frames_fallen=2,
            hysteresis_frames=2,
        )

        frame_candidate_states = []
        for o in obs:
            b = o.bbox
            from app.engines.perception.tracker.track import TrackBBox
            if isinstance(b, TrackBBox):
                x1, y1, x2, y2 = b.x1, b.y1, b.x2, b.y2
            elif hasattr(b, '__len__') and len(b) >= 4:
                x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
            else:
                continue
            if any(v > 1.5 for v in [x1, y1, x2, y2]):
                x1 /= max(w, 1.0); y1 /= max(h, 1.0)
                x2 /= max(w, 1.0); y2 /= max(h, 1.0)
            spf = SimplePoseFrame.from_bbox(
                frame_number=o.frame_number,
                timestamp_ms=o.timestamp_ms,
                track_id=tid,
                x1=x1, y1=y1, x2=x2, y2=y2,
                frame_h=1.0,
            )
            tpa.update(spf)
            # Internal frame features
            if tpa._all_frames:
                frame_candidate_states.append(tpa._all_frames[-1].candidate_state)

        tpa_events = tpa.flush()
        final_pose_state = tpa.current_state
        state_seq = list(tpa._state_sequence)

        # Pose candidate breakdown
        cand_counts = dict(Counter(frame_candidate_states))
        dominant_pose = Counter(frame_candidate_states).most_common(1)[0][0] if frame_candidate_states else 'UNKNOWN'

        record = {
            'track_id': tid,
            'obs_count': n,
            'duration_s': round((obs[-1].timestamp_ms - obs[0].timestamp_ms)/1000.0, 2),
            'start_frame': obs[0].frame_number,
            'end_frame': obs[-1].frame_number,
            'activity_label': act_res.label,
            'activity_confidence': round(act_res.confidence, 3),
            'raw_stair_fires': raw_stair_fires,
            'raw_stair_conf': round(raw_stair_conf, 3),
            'raw_stair_dir': raw_stair_dir,
            'mean_speed': round(mean_speed, 4),
            'final_pose_state': final_pose_state,
            'dominant_pose': dominant_pose,
            'pose_state_sequence': state_seq,
            'pose_candidate_counts': cand_counts,
            'pose_event_count': len(tpa_events),
            'pose_events': [e.event_type for e in tpa_events],
        }
        track_records[tid] = record
        if raw_stair_fires:
            stair_positives.append(record)

    print(f'Total tracks analyzed: {len(track_records)}')
    print(f'Total raw stair positives: {len(stair_positives)}')

    # STEP 3: Known track inspection
    print("\n=== STEP 3: KNOWN AUDIT TRACKS ===")
    known_tracks_report = {}
    for tid in TARGET_TRACKS:
        if tid in track_records:
            r = track_records[tid]
            known_tracks_report[str(tid)] = r
            print(f"Track {tid}: label={r['activity_label']} stair_fires={r['raw_stair_fires']} "
                  f"final_pose={r['final_pose_state']} dom_pose={r['dominant_pose']} "
                  f"seq={r['pose_state_sequence']} cands={r['pose_candidate_counts']}")

    # STEP 4: Correlation between Stair Positives and Temporal Pose
    print("\n=== STEP 4: POSE CORRELATION WITH CURRENT_STAIR_CLASSIFIER_POSITIVES ===")
    upstairs_tracks = [r for r in stair_positives if r['raw_stair_dir'] == 'up']
    downstairs_tracks = [r for r in stair_positives if r['raw_stair_dir'] == 'down']
    non_stair_tracks = [r for r in track_records.values() if not r['raw_stair_fires']]

    def get_pose_dist(records):
        dom_counts = Counter(r['dominant_pose'] for r in records)
        final_counts = Counter(r['final_pose_state'] for r in records)
        all_cand_counts = Counter()
        for r in records:
            for k, v in r['pose_candidate_counts'].items():
                all_cand_counts[k] += v
        return {
            'count': len(records),
            'dominant_pose_distribution': dict(dom_counts),
            'final_pose_distribution': dict(final_counts),
            'total_candidate_frames': dict(all_cand_counts),
        }

    up_dist = get_pose_dist(upstairs_tracks)
    down_dist = get_pose_dist(downstairs_tracks)
    non_stair_dist = get_pose_dist(non_stair_tracks)
    all_stair_dist = get_pose_dist(stair_positives)

    print(f"CURRENT_STAIR_CLASSIFIER_POSITIVES (Total={len(stair_positives)}):")
    print(f"  Dominant Pose: {all_stair_dist['dominant_pose_distribution']}")
    print(f"  Final Pose:    {all_stair_dist['final_pose_distribution']}")
    print(f"Non-Stair Tracks (Total={len(non_stair_tracks)}):")
    print(f"  Dominant Pose: {non_stair_dist['dominant_pose_distribution']}")
    print(f"  Final Pose:    {non_stair_dist['final_pose_distribution']}")

    # Transition pattern analysis
    stair_transitions = Counter()
    for r in stair_positives:
        seq = tuple(r['pose_state_sequence'])
        stair_transitions[str(seq)] += 1
    non_stair_transitions = Counter()
    for r in non_stair_tracks:
        seq = tuple(r['pose_state_sequence'])
        non_stair_transitions[str(seq)] += 1

    print("\nState Sequence Frequency in Stair Positives:")
    for seq_str, cnt in stair_transitions.most_common(5):
        print(f"  {seq_str}: {cnt}")

    # STEP 6: Offline Combination Experiments
    print("\n=== STEP 6: EXISTING-SIGNAL COMBINATION TESTS ===")
    combinations = [
        ("Combo 1: Raw Stair AND Dominant Pose == WALKING",
         lambda r: r['raw_stair_fires'] and r['dominant_pose'] == STATE_WALKING),
        ("Combo 2: Raw Stair AND Final Pose == WALKING",
         lambda r: r['raw_stair_fires'] and r['final_pose_state'] == STATE_WALKING),
        ("Combo 3: Raw Stair AND Dominant Pose in {WALKING, RUNNING}",
         lambda r: r['raw_stair_fires'] and r['dominant_pose'] in (STATE_WALKING, STATE_RUNNING)),
        ("Combo 4: Raw Stair AND Final Pose != STANDING",
         lambda r: r['raw_stair_fires'] and r['final_pose_state'] != STATE_STANDING),
        ("Combo 5: Raw Stair AND Has Pose Transition (len(seq) >= 1)",
         lambda r: r['raw_stair_fires'] and len(r['pose_state_sequence']) >= 1),
        ("Combo 6: Raw Stair AND Dominant Pose == STANDING",
         lambda r: r['raw_stair_fires'] and r['dominant_pose'] == STATE_STANDING),
    ]

    combo_results = {}
    for cname, cfn in combinations:
        passed = [r for r in track_records.values() if cfn(r)]
        passed_up = [r for r in passed if r['raw_stair_dir'] == 'up']
        passed_down = [r for r in passed if r['raw_stair_dir'] == 'down']
        surviving_known = [tid for tid in TARGET_TRACKS if tid in [r['track_id'] for r in passed]]
        rejected_known = [tid for tid in TARGET_TRACKS if tid in track_records and tid not in surviving_known]
        reduction_pct = round(100.0 * (1.0 - len(passed) / max(len(stair_positives), 1)), 1)

        combo_results[cname] = {
            'passed_count': len(passed),
            'upstairs_count': len(passed_up),
            'downstairs_count': len(passed_down),
            'reduction_pct': reduction_pct,
            'surviving_known_tracks': surviving_known,
            'rejected_known_tracks': rejected_known,
            'passed_track_ids': [r['track_id'] for r in passed],
        }
        print(f"\n{cname}:")
        print(f"  passed: {len(passed)} (up={len(passed_up)}, down={len(passed_down)}) -> red: {reduction_pct}%")
        print(f"  known surviving: {surviving_known}")
        print(f"  known rejected:  {rejected_known}")

    output_payload = {
        'phase': '6E.5',
        'baseline_commit': 'f9bc309',
        'total_confirmed_person_tracks_ge_5': len(person_tracks),
        'total_raw_stair_positives': len(stair_positives),
        'known_audit_tracks': known_tracks_report,
        'pose_correlation': {
            'upstairs_distribution': up_dist,
            'downstairs_distribution': down_dist,
            'all_stair_positives_distribution': all_stair_dist,
            'non_stair_distribution': non_stair_dist,
            'stair_state_sequences': dict(stair_transitions),
            'non_stair_state_sequences': dict(non_stair_transitions),
        },
        'existing_signal_combinations': combo_results,
        'all_track_records': track_records,
    }

    with open(OUT_JSON, 'w') as f:
        json.dump(output_payload, f, indent=2, default=str)
    print(f"\nDiagnostic saved to {OUT_JSON}")
    shutil.rmtree(str(tmpdir), ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(run())
