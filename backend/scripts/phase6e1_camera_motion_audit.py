"""
Phase 6E.1 — Per-track camera-motion overlap analysis.

Runs the full pipeline up through S06 on the 300s clip,
then calculates camera-motion frame overlap for audit tracks:
    56, 160, 366, 14, 177

Also extracts ActivityClassifier signals for each track.
"""
import asyncio
import json
import logging
import os
import sys
import shutil
import tempfile
import uuid
from pathlib import Path

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
OUT   = REPO / 'results/TCE-v1.0/phase6e1-camera-motion-audit.json'

AUDIT_TRACKS = {56, 160, 366, 14, 177}

async def run():
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze,
    )
    from app.utils.activity_classifier import (
        ActivityClassifier, RUN_THRESHOLD, WALK_THRESHOLD, STAIR_VERT_THRESHOLD,
        CYCLE_HORIZ_THRESHOLD, STILL_THRESHOLD
    )
    import numpy as np

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6e1_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6E1-%s' % uuid.uuid4().hex[:6].upper()
    print(f'[SETUP] job_id={job_id}')

    # Extract 300s clip
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
        job_id=job_id, video_id='VID-6E1', video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile': 'balanced', 'detection_model': 'yolo11l',
            'detection_confidence': 0.25, 'detection_threshold': 0.25,
            'frame_skip_rate': 5, 'low_light_enabled': True,
            'cycle_threshold': 0.25, 'require_temporal_overlap': True,
        },
    )

    # Run only through S06
    stages = [s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
              s05_track, s06_motion_analyze]

    for mod in stages:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        status = 'OK' if r.success else 'FAIL'
        print(f'  {name}: {status}')
        if not r.success:
            print(f'  ERRORS: {r.errors}'); break

    try:
        all_tracks   = ctx.metadata.get('all_tracks', [])
        camera_frames_list = ctx.metadata.get('camera_motion_frames', [])
        camera_frames = set(camera_frames_list)
        motion_profiles = ctx.metadata.get('motion_profiles', {})
        track_activities = ctx.metadata.get('track_activities', {})

        print(f'\n[RESULT] camera_motion_frames: {len(camera_frames_list)}')
        if camera_frames_list:
            print(f'  first 20: {sorted(camera_frames_list)[:20]}')
            print(f'  last  10: {sorted(camera_frames_list)[-10:]}')

        track_map = {t.track_id: t for t in all_tracks}

        # Re-run ActivityClassifier with experimental settings
        clf = ActivityClassifier(fps=fps, frame_skip=5, cycle_threshold=0.25,
                                 require_temporal_overlap=True)

        results = {}
        for tid in sorted(AUDIT_TRACKS):
            track = track_map.get(tid)
            if track is None:
                print(f'\n[TRACK {tid}] NOT FOUND')
                results[tid] = {'error': 'track_not_found'}
                continue

            obs = track.observations
            track_frame_nums = {o.frame_number for o in obs}
            cam_overlap_frames = track_frame_nums & camera_frames
            cam_overlap_pct = (
                100.0 * len(cam_overlap_frames) / len(track_frame_nums)
                if track_frame_nums else 0.0
            )
            entirely_in_cam = track_frame_nums.issubset(camera_frames)

            # Classify
            activity = clf.classify(track, all_tracks=all_tracks)

            # Compute velocity signals manually for evidence
            import numpy as np
            dt = 5 / max(fps, 1.0)
            vx_list, vy_list, speed_list = [], [], []
            for i in range(1, len(obs)):
                dx = obs[i].bbox.cx - obs[i-1].bbox.cx
                dy = obs[i].bbox.cy - obs[i-1].bbox.cy
                vx_list.append(dx / dt)
                vy_list.append(dy / dt)
                speed_list.append(np.sqrt(dx**2 + dy**2) / dt)

            vx_arr = np.array(vx_list) if vx_list else np.array([0.0])
            vy_arr = np.array(vy_list) if vy_list else np.array([0.0])
            sp_arr = np.array(speed_list) if speed_list else np.array([0.0])

            n_vy_up   = int(np.sum(vy_arr < -STAIR_VERT_THRESHOLD))
            n_vy_down = int(np.sum(vy_arr > STAIR_VERT_THRESHOLD))
            vy_up_frac = n_vy_up / max(len(vy_arr), 1)

            mean_speed = float(np.mean(sp_arr))
            mean_vy    = float(np.mean(vy_arr))
            mean_vx    = float(np.mean(np.abs(vx_arr)))
            speed_std  = float(np.std(sp_arr))

            # Frame range
            frame_nums_sorted = sorted(track_frame_nums)

            print(f'\n[TRACK {tid}] activity={activity.label}  conf={activity.confidence:.3f}')
            print(f'  obs={len(obs)}  frames={frame_nums_sorted[0]}–{frame_nums_sorted[-1]}')
            print(f'  start_ms={obs[0].timestamp_ms:.0f}  end_ms={obs[-1].timestamp_ms:.0f}')
            print(f'  mean_speed={mean_speed:.5f}  RUN_THRESHOLD={RUN_THRESHOLD}')
            print(f'  mean_vy={mean_vy:.5f}  STAIR_VERT_THRESHOLD={STAIR_VERT_THRESHOLD}')
            print(f'  n_vy_up={n_vy_up}  n_vy_down={n_vy_down}  vy_up_frac={vy_up_frac:.2%}')
            print(f'  cam_overlap_frames={len(cam_overlap_frames)}/{len(track_frame_nums)}  ({cam_overlap_pct:.1f}%)')
            print(f'  entirely_in_cam_frames={entirely_in_cam}')
            print(f'  would_be_suppressed_by_pass1={entirely_in_cam}')
            print(f'  cam_overlap_frames_list={sorted(cam_overlap_frames)[:10]}')

            results[tid] = {
                'track_id': tid,
                'activity_label': activity.label,
                'activity_confidence': round(activity.confidence, 3),
                'obs_count': len(obs),
                'frame_range': [frame_nums_sorted[0], frame_nums_sorted[-1]],
                'start_ms': round(obs[0].timestamp_ms, 1),
                'end_ms': round(obs[-1].timestamp_ms, 1),
                'mean_speed': round(mean_speed, 5),
                'run_threshold': RUN_THRESHOLD,
                'mean_vy': round(mean_vy, 5),
                'mean_abs_vx': round(mean_vx, 5),
                'stair_vert_threshold': STAIR_VERT_THRESHOLD,
                'n_vy_up': n_vy_up,
                'n_vy_down': n_vy_down,
                'vy_up_fraction': round(vy_up_frac, 4),
                'speed_std': round(speed_std, 5),
                'camera_motion_frame_count': len(camera_frames_list),
                'track_frames_count': len(track_frame_nums),
                'cam_overlap_frames_count': len(cam_overlap_frames),
                'cam_overlap_pct': round(cam_overlap_pct, 1),
                'entirely_in_cam_frames': entirely_in_cam,
                'would_be_suppressed_pass1': entirely_in_cam,
                'cam_overlap_frame_numbers': sorted(cam_overlap_frames)[:20],
            }

        final = {
            'phase': '6E.1',
            'total_camera_motion_frames': len(camera_frames_list),
            'camera_motion_frame_numbers_sample': sorted(camera_frames_list)[:30],
            'audit_tracks': results,
        }
        with open(OUT, 'w') as fh:
            json.dump(final, fh, indent=2, default=str)
        print(f'\nSaved: {OUT}')

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == '__main__':
    asyncio.run(run())
