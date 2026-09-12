"""
Phase 6D.2 — Cycling Classifier Feature Extraction.

Replays S01-S09 on archive_001 300s to extract per-track cycling features.
Uses the SAME configuration as Phase 6B/6D. No pipeline changes.

This is a diagnostic-only run — we need track.observations to compute
the same features ActivityClassifier computes, for ALL tracks,
not just those that became cycling events.

Outputs:
  results/TCE-v1.0/phase6d2-cycling-track-features.json
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
OUT = REPO / 'results/TCE-v1.0/phase6d2-cycling-track-features.json'

# Exact thresholds from activity_classifier.py — do NOT change
STILL_THRESHOLD       = 0.003
WALK_THRESHOLD        = 0.008
RUN_THRESHOLD         = 0.022
CYCLE_HORIZ_THRESHOLD = 0.018
BICYCLE_CLASSES       = {"bicycle", "bike", "cycle", "motorbike", "motorcycle", "scooter"}
FPS = 30.0
FRAME_SKIP = 5
DT = FRAME_SKIP / FPS  # 0.1667s


def compute_track_features(track, all_tracks):
    """Compute the exact same features ActivityClassifier uses, for diagnostics."""
    obs = track.observations
    if len(obs) < 3:
        return None

    # Velocity
    vx_list, vy_list, speed_list = [], [], []
    for i in range(1, len(obs)):
        dx = obs[i].bbox.cx - obs[i - 1].bbox.cx
        dy = obs[i].bbox.cy - obs[i - 1].bbox.cy
        vx_list.append(dx / DT)
        vy_list.append(dy / DT)
        speed_list.append(np.sqrt(dx * dx + dy * dy) / DT)

    vx_arr  = np.array(vx_list)
    vy_arr  = np.array(vy_list)
    spd_arr = np.array(speed_list)

    mean_speed  = float(np.mean(spd_arr))
    max_speed   = float(np.max(spd_arr))
    speed_std   = float(np.std(spd_arr))
    mean_vy     = float(np.mean(vy_arr))
    mean_abs_vx = float(np.mean(np.abs(vx_arr)))

    # Heights
    heights = [o.bbox.height for o in obs]
    height_mean = float(np.mean(heights))
    height_std  = float(np.std(heights))
    height_min  = float(np.min(heights))
    height_max  = float(np.max(heights))

    # Widths
    widths = [o.bbox.width for o in obs]
    width_mean = float(np.mean(widths))
    width_std  = float(np.std(widths))

    # Spatial displacement
    cxs = [o.bbox.cx for o in obs]
    cys = [o.bbox.cy for o in obs]
    horiz_disp = abs(cxs[-1] - cxs[0])
    vert_disp  = abs(cys[-1] - cys[0])
    total_disp = float(np.sqrt(horiz_disp**2 + vert_disp**2))
    disp_ratio = horiz_disp / max(vert_disp, 1e-6)  # >1 = mostly horizontal

    # Detection confidence
    confs = [getattr(o, 'confidence', 0.0) or 0.0 for o in obs]
    det_conf_mean = float(np.mean(confs)) if confs else 0.0

    # Track duration
    duration_ms = obs[-1].timestamp_ms - obs[0].timestamp_ms

    # Signal 1: bicycle proximity
    bicycle_tracks = [
        t for t in all_tracks
        if (t.class_name or '').lower() in BICYCLE_CLASSES and t.is_confirmed
    ]
    signal1_conf = 0.0
    signal1_dist = None
    if bicycle_tracks and obs:
        person_cxs = np.array([o.bbox.cx for o in obs])
        person_cys = np.array([o.bbox.cy for o in obs])
        for bt in bicycle_tracks:
            if not bt.observations:
                continue
            bike_cxs = np.array([o.bbox.cx for o in bt.observations])
            bike_cys = np.array([o.bbox.cy for o in bt.observations])
            dist = float(np.sqrt(
                (np.mean(person_cxs) - np.mean(bike_cxs))**2
                + (np.mean(person_cys) - np.mean(bike_cys))**2
            ))
            if dist < 0.25:
                s1c = max(0.70, 0.95 - dist * 2)
                if s1c > signal1_conf:
                    signal1_conf = s1c
                    signal1_dist = dist

    # Signal 2: speed + height stability
    signal2_speed_trigger = mean_speed >= CYCLE_HORIZ_THRESHOLD
    signal2_height_trigger = height_std < 0.03
    signal2_fires = signal2_speed_trigger and signal2_height_trigger
    signal2_conf = 0.65 if signal2_fires else 0.0

    # Final cycling conf (same logic as ActivityClassifier._detect_cycling)
    cycling_conf = max(signal1_conf, signal2_conf)
    is_classified_cycling = cycling_conf >= 0.60

    return {
        'track_id': track.track_id,
        'class_name': track.class_name,
        'is_confirmed': track.is_confirmed,
        'obs_count': len(obs),
        'duration_ms': round(duration_ms, 1),
        'duration_s': round(duration_ms / 1000, 2),
        # Speed features
        'mean_speed': round(mean_speed, 5),
        'max_speed': round(max_speed, 5),
        'speed_std': round(speed_std, 5),
        'mean_abs_vx': round(mean_abs_vx, 5),
        'mean_vy': round(mean_vy, 5),
        # Height features
        'height_mean': round(height_mean, 4),
        'height_std': round(height_std, 5),
        'height_min': round(height_min, 4),
        'height_max': round(height_max, 4),
        # Width features
        'width_mean': round(width_mean, 4),
        'width_std': round(width_std, 5),
        # Displacement
        'horiz_disp': round(horiz_disp, 4),
        'vert_disp': round(vert_disp, 4),
        'total_disp': round(total_disp, 4),
        'disp_ratio': round(disp_ratio, 3),
        # Detection quality
        'det_conf_mean': round(det_conf_mean, 3),
        # Signal 1
        'signal1_conf': round(signal1_conf, 3),
        'signal1_dist': round(signal1_dist, 4) if signal1_dist is not None else None,
        'signal1_fires': signal1_conf >= 0.60,
        # Signal 2 (ablation)
        'signal2_speed_trigger': signal2_speed_trigger,
        'signal2_height_trigger': signal2_height_trigger,
        'signal2_fires': signal2_fires,
        'signal2_conf': signal2_conf,
        # Combined
        'cycling_conf': round(cycling_conf, 3),
        'is_classified_cycling': is_classified_cycling,
        # Margin to threshold
        'speed_margin_to_threshold': round(mean_speed - CYCLE_HORIZ_THRESHOLD, 5),
        'height_margin_to_threshold': round(0.03 - height_std, 5),
        # Timestamps
        'start_ms': round(obs[0].timestamp_ms, 1),
        'end_ms': round(obs[-1].timestamp_ms, 1),
        'start_s': round(obs[0].timestamp_ms / 1000, 2),
    }


async def run_to_s05():
    """Run S01-S05 only — enough to get Track objects with observations."""
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect,
        s04_object_detect, s05_track,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6d2_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')

    print('[SETUP] Extracting 300s clip...')
    clip_path = str(tmpdir / 'clip.mp4')
    cap = cv2.VideoCapture(str(VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    n_frames = int(fps * 300)
    out = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    i = 0
    while i < n_frames:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame); i += 1
    cap.release(); out.release()
    print(f'[SETUP] Wrote {i} frames @ {fps:.1f}fps')

    ctx = PipelineContext(
        job_id='6D2-FEAT-%s' % uuid.uuid4().hex[:6].upper(),
        video_id='VID-6D2',
        video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile':        'balanced',
            'detection_model':      'yolo11l',
            'detection_confidence': 0.25,
            'detection_threshold':  0.25,
            'frame_skip_rate':      5,
            'low_light_enabled':    True,
        },
    )
    for mod in (s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track):
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        print(f'  {name}: {"OK" if r.success else "FAIL"}')
        if not r.success:
            print(f'  ERR: {r.errors}')
            break

    return ctx, tmpdir


async def main():
    print('Phase 6D.2 — Cycling classifier feature extraction')
    print('Running S01–S05 on archive_001 300s (same config as Phase 6B/6D)...')
    print()

    ctx, tmpdir = await run_to_s05()

    try:
        all_tracks = ctx.metadata.get('all_tracks', [])
        print(f'\n[FEATURES] Total tracks: {len(all_tracks)}')

        person_tracks = [t for t in all_tracks
                         if (t.class_name or '').lower() in
                         {'person', 'man', 'woman', 'child', 'baby'}]
        confirmed_persons = [t for t in person_tracks if t.is_confirmed]
        print(f'[FEATURES] Person tracks: {len(person_tracks)} ({len(confirmed_persons)} confirmed)')

        # Compute features for all tracks with >=3 observations
        features = []
        skipped = 0
        for t in all_tracks:
            f = compute_track_features(t, all_tracks)
            if f is None:
                skipped += 1
                continue
            features.append(f)

        cycling = [f for f in features if f['is_classified_cycling']]
        non_cycling = [f for f in features if not f['is_classified_cycling']]

        print(f'[FEATURES] Tracks with >=3 obs: {len(features)} ({skipped} skipped)')
        print(f'[FEATURES] Classified cycling: {len(cycling)}')
        print(f'[FEATURES] Not cycling: {len(non_cycling)}')

        # Signal ablation counts
        speed_only = sum(1 for f in features if f['signal2_speed_trigger'])
        height_only = sum(1 for f in features if f['signal2_height_trigger'])
        both = sum(1 for f in features if f['signal2_fires'])
        signal1_fires = sum(1 for f in features if f['signal1_fires'])

        print(f'\n[ABLATION] Signal 2 speed trigger (speed>=0.018): {speed_only}/{len(features)} = {100*speed_only/max(len(features),1):.1f}%')
        print(f'[ABLATION] Signal 2 height trigger (height_std<0.03): {height_only}/{len(features)} = {100*height_only/max(len(features),1):.1f}%')
        print(f'[ABLATION] Signal 2 both (speed+height): {both}/{len(features)} = {100*both/max(len(features),1):.1f}%')
        print(f'[ABLATION] Signal 1 fires (bicycle proximity): {signal1_fires}/{len(features)} = {100*signal1_fires/max(len(features),1):.1f}%')

        # Stats for cycling vs non-cycling
        def stats(vals, name):
            if not vals:
                return {'n': 0}
            a = np.array(vals)
            return {
                'n': len(vals),
                'min': round(float(np.min(a)), 5),
                'p25': round(float(np.percentile(a, 25)), 5),
                'median': round(float(np.median(a)), 5),
                'mean': round(float(np.mean(a)), 5),
                'p75': round(float(np.percentile(a, 75)), 5),
                'max': round(float(np.max(a)), 5),
                'std': round(float(np.std(a)), 5),
            }

        print('\n[STATS] mean_speed distribution (all tracks with >=3 obs):')
        all_speeds = [f['mean_speed'] for f in features]
        s = stats(all_speeds, 'mean_speed')
        print(f'  min={s["min"]}  p25={s["p25"]}  median={s["median"]}  mean={s["mean"]}  p75={s["p75"]}  max={s["max"]}')
        print(f'  CYCLE_HORIZ_THRESHOLD=0.018 — tracks ABOVE: {sum(1 for v in all_speeds if v>=0.018)}/{len(all_speeds)} = {100*sum(1 for v in all_speeds if v>=0.018)/max(len(all_speeds),1):.1f}%')

        print('\n[STATS] height_std distribution (all tracks with >=3 obs):')
        all_hstd = [f['height_std'] for f in features]
        s2 = stats(all_hstd, 'height_std')
        print(f'  min={s2["min"]}  p25={s2["p25"]}  median={s2["median"]}  mean={s2["mean"]}  p75={s2["p75"]}  max={s2["max"]}')
        print(f'  height_std<0.03 — tracks BELOW: {sum(1 for v in all_hstd if v<0.03)}/{len(all_hstd)} = {100*sum(1 for v in all_hstd if v<0.03)/max(len(all_hstd),1):.1f}%')

        # Save full output
        result = {
            'phase': 'Phase 6D.2',
            'baseline_commit': 'bd9d18e',
            'dataset': 'archive_001',
            'clip_s': 300,
            'config': {'fps': FPS, 'frame_skip': FRAME_SKIP, 'dt': DT,
                       'cycle_horiz_threshold': CYCLE_HORIZ_THRESHOLD,
                       'still_threshold': STILL_THRESHOLD,
                       'walk_threshold': WALK_THRESHOLD,
                       'run_threshold': RUN_THRESHOLD},
            'counts': {
                'total_tracks': len(all_tracks),
                'tracks_with_min_obs': len(features),
                'skipped_under_3obs': skipped,
                'classified_cycling': len(cycling),
                'not_cycling': len(non_cycling),
            },
            'ablation': {
                'signal1_bicycle_proximity': signal1_fires,
                'signal2_speed_only': speed_only,
                'signal2_height_only': height_only,
                'signal2_both_speed_and_height': both,
            },
            'speed_distribution': stats([f['mean_speed'] for f in features], 'speed'),
            'height_std_distribution': stats([f['height_std'] for f in features], 'height_std'),
            'cycling_speed_distribution': stats([f['mean_speed'] for f in cycling], 'speed'),
            'cycling_height_std_distribution': stats([f['height_std'] for f in cycling], 'height_std'),
            'noncycling_speed_distribution': stats([f['mean_speed'] for f in non_cycling], 'speed'),
            'noncycling_height_std_distribution': stats([f['height_std'] for f in non_cycling], 'height_std'),
            'all_track_features': features,
        }

        with open(OUT, 'w') as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f'\nSaved: {OUT}')

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == '__main__':
    asyncio.run(main())
