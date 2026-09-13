"""
Phase 6E.3 — Scene-Geometry and Population Vertical Velocity Diagnostic.

Executes S01–S06 on archive_001 300s, collects full track kinematics,
groups tracks by scene intervals and temporal coexistence, evaluates
population-level vertical velocity, and tests offline normalization.
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
import numpy as np

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
OUT_JSON = REPO / 'results/TCE-v1.0/phase6e3-scene-geometry-diagnostic.json'

TARGET_AUDIT_TRACKS = [160, 177, 252, 273, 14, 56]


def evaluate_stairs(vy_arr: np.ndarray, mean_speed: float, threshold: float = 0.005) -> tuple[float, str, bool]:
    """Offline replica of ActivityClassifier._detect_stairs with configurable threshold."""
    if len(vy_arr) < 4:
        return 0.0, "up", False

    n_up = int(np.sum(vy_arr < -threshold))
    n_down = int(np.sum(vy_arr > threshold))
    n_total = len(vy_arr)

    mean_vy_abs = float(np.mean(np.abs(vy_arr)))

    if n_up > n_down:
        dominant_frac = n_up / n_total
        direction = "up"
    else:
        dominant_frac = n_down / n_total
        direction = "down"

    if dominant_frac < 0.50:
        return 0.0, direction, False

    magnitude_factor = min(1.0, mean_vy_abs / (threshold * 3))
    confidence = dominant_frac * 0.6 + magnitude_factor * 0.4

    if mean_speed < 0.008 * 0.5:
        confidence *= 0.5

    conf = min(0.93, confidence)
    fires = (conf >= 0.55 and mean_speed >= 0.008)
    return conf, direction, fires


async def run():
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze,
    )
    from app.utils.activity_classifier import ActivityClassifier

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6e3_diag_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6E3-%s' % uuid.uuid4().hex[:6].upper()
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
        job_id=job_id, video_id='VID-6E3-DIAG', video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile': 'balanced', 'detection_model': 'yolo11l',
            'detection_confidence': 0.25, 'detection_threshold': 0.25,
            'frame_skip_rate': 5, 'low_light_enabled': True,
            'cycle_threshold': 0.25, 'require_temporal_overlap': True,
            'min_activity_observations': 5,
        },
    )

    for mod in [s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track, s06_motion_analyze]:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        print(f'  {name}: {"OK" if r.success else "FAIL"}')
        if not r.success:
            print(f'  ERRORS: {r.errors}'); return

    all_tracks = ctx.metadata.get('all_tracks', [])
    scene_boundaries = ctx.metadata.get('scene_boundaries', [])
    camera_motion_frames = set(ctx.metadata.get('camera_motion_frames', []))
    dt = 5 / max(fps, 1.0)

    _HUMAN_CLASSES = {"person", "man", "woman", "child", "baby", "crowd"}
    person_tracks = [
        t for t in all_tracks
        if (t.is_confirmed or t.confirmed_at_frame is not None)
        and (t.class_name or "").lower() in _HUMAN_CLASSES
        and len(t.observations) >= 5  # Phase 6E.2 guard
    ]
    print(f'\nTotal confirmed person tracks (obs >= 5): {len(person_tracks)}')

    # Build scene intervals from boundaries
    scene_intervals = []
    # Scene boundaries are extracted frame numbers
    sorted_bounds = sorted(set([0] + scene_boundaries + [int(n_frames / 5)]))
    for idx in range(len(sorted_bounds) - 1):
        scene_intervals.append((sorted_bounds[idx], sorted_bounds[idx + 1]))

    clf = ActivityClassifier(fps=fps, frame_skip=5, cycle_threshold=0.25,
                             require_temporal_overlap=True, min_activity_observations=5)

    track_records = {}
    for t in person_tracks:
        obs = t.observations
        fn_start = obs[0].frame_number
        fn_end = obs[-1].frame_number

        # Map to scene index
        scene_idx = 0
        for s_i, (s_start, s_end) in enumerate(scene_intervals):
            if fn_start >= s_start and fn_start <= s_end:
                scene_idx = s_i
                break

        # Compute velocities
        vx_list, vy_list, speed_list = [], [], []
        for j in range(1, len(obs)):
            dx = obs[j].bbox.cx - obs[j - 1].bbox.cx
            dy = obs[j].bbox.cy - obs[j - 1].bbox.cy
            vx_list.append(dx / dt)
            vy_list.append(dy / dt)
            speed_list.append(np.sqrt(dx * dx + dy * dy) / dt)

        vx_arr = np.array(vx_list)
        vy_arr = np.array(vy_list)
        spd_arr = np.array(speed_list)

        mean_speed = float(np.mean(spd_arr))
        mean_vx = float(np.mean(np.abs(vx_arr)))
        mean_vy = float(np.mean(vy_arr))
        vy_std = float(np.std(vy_arr))

        heights = [o.bbox.height for o in obs]
        widths = [o.bbox.width for o in obs]

        act_res = clf.classify(t, all_tracks=all_tracks)
        raw_stair_conf, raw_stair_dir, raw_stair_fires = evaluate_stairs(vy_arr, mean_speed)

        # Camera motion overlap
        track_frames = {o.frame_number for o in obs}
        cam_overlap = len(track_frames & camera_motion_frames) / max(len(track_frames), 1)

        track_records[t.track_id] = {
            'track_id': t.track_id,
            'scene_index': scene_idx,
            'obs_count': len(obs),
            'frame_range': [fn_start, fn_end],
            'time_range_s': [round(obs[0].timestamp_ms / 1000, 2), round(obs[-1].timestamp_ms / 1000, 2)],
            'duration_s': round((obs[-1].timestamp_ms - obs[0].timestamp_ms) / 1000, 2),
            'mean_speed': round(mean_speed, 5),
            'mean_vx': round(mean_vx, 5),
            'mean_vy': round(mean_vy, 5),
            'vy_std': round(vy_std, 5),
            'height_mean': round(float(np.mean(heights)), 4),
            'height_std': round(float(np.std(heights)), 4),
            'width_mean': round(float(np.mean(widths)), 4),
            'width_std': round(float(np.std(widths)), 4),
            'start_cx_cy': [round(obs[0].bbox.cx, 4), round(obs[0].bbox.cy, 4)],
            'end_cx_cy': [round(obs[-1].bbox.cx, 4), round(obs[-1].bbox.cy, 4)],
            'total_dx': round(obs[-1].bbox.cx - obs[0].bbox.cx, 4),
            'total_dy': round(obs[-1].bbox.cy - obs[0].bbox.cy, 4),
            'activity_label': act_res.label,
            'activity_confidence': act_res.confidence,
            'raw_stair_conf': round(raw_stair_conf, 3),
            'raw_stair_dir': raw_stair_dir,
            'raw_stair_fires': raw_stair_fires,
            'camera_motion_overlap_pct': round(cam_overlap * 100, 1),
            '_vy_list': [float(v) for v in vy_list],
            '_mean_speed': mean_speed,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Scene Population Analysis
    # ──────────────────────────────────────────────────────────────────────────
    scenes_stats = {}
    for s_idx in range(len(scene_intervals)):
        scene_tids = [tid for tid, rec in track_records.items() if rec['scene_index'] == s_idx]
        if not scene_tids:
            continue
        vys = [track_records[tid]['mean_vy'] for tid in scene_tids]
        scenes_stats[s_idx] = {
            'scene_index': s_idx,
            'interval_frames': scene_intervals[s_idx],
            'track_count': len(scene_tids),
            'track_ids': scene_tids,
            'population_mean_vy': round(float(np.mean(vys)), 5),
            'population_median_vy': round(float(np.median(vys)), 5),
            'population_std_vy': round(float(np.std(vys)), 5),
        }

    print("\n=== SCENE POPULATION STATS ===")
    for s_idx, sdata in scenes_stats.items():
        if sdata['track_count'] >= 2:
            print(f"Scene {s_idx} (frames {sdata['interval_frames']}): tracks={sdata['track_count']} "
                  f"mean_vy={sdata['population_mean_vy']:.5f} median_vy={sdata['population_median_vy']:.5f} std_vy={sdata['population_std_vy']:.5f}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Test Normalization Hypothesis Offline
    # ──────────────────────────────────────────────────────────────────────────
    raw_stair_fires_count = 0
    mean_norm_stair_fires_count = 0
    median_norm_stair_fires_count = 0

    norm_evaluations = {}

    for tid, rec in track_records.items():
        s_idx = rec['scene_index']
        pop_stat = scenes_stats.get(s_idx, {})
        n_tracks = pop_stat.get('track_count', 1)

        pop_mean = pop_stat.get('population_mean_vy', 0.0)
        pop_median = pop_stat.get('population_median_vy', 0.0)

        # Raw evaluation
        vy_arr = np.array(rec['_vy_list'])
        mean_speed = rec['_mean_speed']

        raw_conf, raw_dir, raw_fire = evaluate_stairs(vy_arr, mean_speed)
        if raw_fire: raw_stair_fires_count += 1

        # Only normalize if population has at least 2 tracks
        if n_tracks >= 2:
            # Mean-centered vy_arr
            vy_mean_norm = vy_arr - pop_mean
            m_conf, m_dir, m_fire = evaluate_stairs(vy_mean_norm, mean_speed)

            # Median-centered vy_arr
            vy_med_norm = vy_arr - pop_median
            med_conf, med_dir, med_fire = evaluate_stairs(vy_med_norm, mean_speed)
        else:
            m_conf, m_dir, m_fire = raw_conf, raw_dir, raw_fire
            med_conf, med_dir, med_fire = raw_conf, raw_dir, raw_fire

        if m_fire: mean_norm_stair_fires_count += 1
        if med_fire: median_norm_stair_fires_count += 1

        norm_evaluations[tid] = {
            'track_id': tid,
            'scene_index': s_idx,
            'tracks_in_scene': n_tracks,
            'raw_mean_vy': rec['mean_vy'],
            'pop_mean_vy': pop_mean,
            'pop_median_vy': pop_median,
            'norm_mean_vy': round(rec['mean_vy'] - pop_mean, 5),
            'norm_median_vy': round(rec['mean_vy'] - pop_median, 5),
            'raw_stair_fires': raw_fire,
            'raw_stair_dir': raw_dir,
            'raw_stair_conf': round(raw_conf, 3),
            'mean_norm_stair_fires': m_fire,
            'mean_norm_stair_dir': m_dir,
            'mean_norm_stair_conf': round(m_conf, 3),
            'median_norm_stair_fires': med_fire,
            'median_norm_stair_dir': med_dir,
            'median_norm_stair_conf': round(med_conf, 3),
        }

    print("\n=== STAIRS NORMALIZATION SUMMARY ===")
    print(f"Raw stair triggers:           {raw_stair_fires_count}")
    print(f"Mean-normalized triggers:     {mean_norm_stair_fires_count}")
    print(f"Median-normalized triggers:   {median_norm_stair_fires_count}")

    print("\n=== TARGET AUDIT TRACKS COMPARISON ===")
    target_results = {}
    for tid in TARGET_AUDIT_TRACKS:
        ev = norm_evaluations.get(tid)
        rec = track_records.get(tid)
        if not ev:
            print(f"Track {tid}: NOT FOUND in records (obs < 5 or not person)")
            continue
        print(f"Track {tid} (scene {ev['scene_index']}, {ev['tracks_in_scene']} tracks in scene, label={rec['activity_label']}):")
        print(f"  raw: mean_vy={ev['raw_mean_vy']:.5f}  fires={ev['raw_stair_fires']} ({ev['raw_stair_dir']}, conf={ev['raw_stair_conf']})")
        print(f"  mean_norm: vy={ev['norm_mean_vy']:.5f}  fires={ev['mean_norm_stair_fires']} ({ev['mean_norm_stair_dir']}, conf={ev['mean_norm_stair_conf']})")
        print(f"  median_norm: vy={ev['norm_median_vy']:.5f}  fires={ev['median_norm_stair_fires']} ({ev['median_norm_stair_dir']}, conf={ev['median_norm_stair_conf']})")
        target_results[tid] = {**ev, 'activity_label': rec['activity_label'], 'obs_count': rec['obs_count']}

    # Clean temporary raw lists before saving
    for r in track_records.values():
        r.pop('_vy_list', None)
        r.pop('_mean_speed', None)

    final_payload = {
        'phase': '6E.3',
        'baseline_commit': '0bd6b70',
        'total_confirmed_person_tracks_ge_5': len(person_tracks),
        'scenes_count': len(scenes_stats),
        'scenes_stats': scenes_stats,
        'normalization_summary': {
            'raw_stair_triggers': raw_stair_fires_count,
            'mean_norm_stair_triggers': mean_norm_stair_fires_count,
            'median_norm_stair_triggers': median_norm_stair_fires_count,
        },
        'target_audit_tracks': target_results,
        'all_track_records': track_records,
        'norm_evaluations': norm_evaluations,
    }

    with open(OUT_JSON, 'w') as f:
        json.dump(final_payload, f, indent=2, default=str)
    print(f"\nSaved diagnostic to {OUT_JSON}")
    shutil.rmtree(str(tmpdir), ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(run())
