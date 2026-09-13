"""
Phase 6E.4 — Posture-Gated Stair Classification Offline Diagnostic.

Runs S01–S05 on archive_001 300s, extracts full observation-level posture
and velocity features for all confirmed person tracks with obs >= 5.
Performs:
- Step 2: Feature extraction (height, width, aspect ratio, vy, temporal consistency)
- Step 3: Analysis of known false-positive tracks (160, 177, 252, 273, 14, 56, 234)
- Step 4: Population-level distribution comparison
- Step 5: Offline evaluation of candidate posture gates (A, B, C, D)
- Step 6: Selection of representative tracks for visual audit
Saves full results to results/TCE-v1.0/phase6e4-posture-stair-diagnostic.json.
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
OUT_JSON = REPO / 'results/TCE-v1.0/phase6e4-posture-stair-diagnostic.json'

TARGET_TRACKS = [160, 177, 252, 273, 14, 56, 234]


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

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6e4_diag_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6E4-%s' % uuid.uuid4().hex[:6].upper()
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
        job_id=job_id, video_id='VID-6E4-DIAG', video_path=clip_path,
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
        fps=fps, frame_skip=5, cycle_threshold=0.25,
        require_temporal_overlap=True, min_activity_observations=5,
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Extract track-level posture & velocity features
    # ──────────────────────────────────────────────────────────────────────────
    feature_records = {}
    for t in person_tracks:
        obs = t.observations
        n_obs = len(obs)

        # Centroid & Box histories
        cxs = [o.bbox.cx for o in obs]
        cys = [o.bbox.cy for o in obs]
        heights = [o.bbox.height for o in obs]
        widths = [o.bbox.width for o in obs]
        aspect_ratios = [w / max(h, 1e-6) for w, h in zip(widths, heights)]

        # Velocities
        vx_list, vy_list, speed_list = [], [], []
        for j in range(1, n_obs):
            dx = cxs[j] - cxs[j - 1]
            dy = cys[j] - cys[j - 1]
            vx_list.append(dx / dt)
            vy_list.append(dy / dt)
            speed_list.append(np.sqrt(dx * dx + dy * dy) / dt)

        vx_arr = np.array(vx_list)
        vy_arr = np.array(vy_list)
        spd_arr = np.array(speed_list)

        mean_speed = float(np.mean(spd_arr))
        max_speed = float(np.max(spd_arr))
        speed_std = float(np.std(spd_arr))
        mean_vx = float(np.mean(np.abs(vx_arr)))
        mean_vy = float(np.mean(vy_arr))
        std_vy = float(np.std(vy_arr))
        abs_mean_vy = float(np.mean(np.abs(vy_arr)))

        # Bbox Height statistics
        h_mean = float(np.mean(heights))
        h_std = float(np.std(heights))
        norm_h_std = h_std / max(h_mean, 1e-6)

        # Bbox Width statistics
        w_mean = float(np.mean(widths))
        w_std = float(np.std(widths))

        # Aspect Ratio statistics
        ar_mean = float(np.mean(aspect_ratios))
        ar_std = float(np.std(aspect_ratios))
        ar_change = float(abs(aspect_ratios[-1] - aspect_ratios[0]))

        # Displacements
        total_dx = cxs[-1] - cxs[0]
        total_dy = cys[-1] - cys[0]

        # Temporal vertical consistency
        n_up = int(np.sum(vy_arr < -STAIR_VERT_THRESHOLD))
        n_down = int(np.sum(vy_arr > STAIR_VERT_THRESHOLD))
        n_total = len(vy_arr)
        dominant_dir = "up" if n_up > n_down else "down"
        dominant_frac = max(n_up, n_down) / max(n_total, 1)
        prop_satisfying_thresh = (n_up + n_down) / max(n_total, 1)

        # Production classification
        act_res = clf.classify(t, all_tracks=all_tracks)

        # Raw stair detection calculation
        stair_fires = False
        raw_stair_conf = 0.0
        if dominant_frac >= 0.50 and len(vy_arr) >= 4:
            mag_factor = min(1.0, abs_mean_vy / (STAIR_VERT_THRESHOLD * 3))
            c = dominant_frac * 0.6 + mag_factor * 0.4
            if mean_speed < WALK_THRESHOLD * 0.5:
                c *= 0.5
            raw_stair_conf = min(0.93, c)
            stair_fires = (raw_stair_conf >= 0.55 and mean_speed >= WALK_THRESHOLD)

        feature_records[t.track_id] = {
            'track_id': t.track_id,
            'obs_count': n_obs,
            'duration_s': round((obs[-1].timestamp_ms - obs[0].timestamp_ms) / 1000, 2),
            'start_frame': obs[0].frame_number,
            'end_frame': obs[-1].frame_number,
            'mean_speed': round(mean_speed, 5),
            'max_speed': round(max_speed, 5),
            'speed_std': round(speed_std, 5),
            'mean_vx': round(mean_vx, 5),
            'mean_vy': round(mean_vy, 5),
            'std_vy': round(std_vy, 5),
            'abs_mean_vy': round(abs_mean_vy, 5),
            'height_mean': round(h_mean, 4),
            'height_std': round(h_std, 4),
            'norm_height_std': round(norm_h_std, 4),
            'width_mean': round(w_mean, 4),
            'width_std': round(w_std, 4),
            'aspect_ratio_mean': round(ar_mean, 4),
            'aspect_ratio_std': round(ar_std, 4),
            'aspect_ratio_change': round(ar_change, 4),
            'total_dx': round(total_dx, 4),
            'total_dy': round(total_dy, 4),
            'dominant_direction': dominant_dir,
            'dominant_fraction': round(dominant_frac, 4),
            'prop_satisfying_thresh': round(prop_satisfying_thresh, 4),
            'activity_label': act_res.label,
            'activity_confidence': act_res.confidence,
            'raw_stair_conf': round(raw_stair_conf, 3),
            'raw_stair_fires': stair_fires,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Analyze known false-positive tracks
    # ──────────────────────────────────────────────────────────────────────────
    print("\n=== STEP 3: KNOWN FALSE-POSITIVE TRACKS ===")
    known_analysis = {}
    for tid in TARGET_TRACKS:
        rec = feature_records.get(tid)
        if not rec:
            print(f"Track {tid}: not found or obs < 5")
            continue
        print(f"\nTrack {tid} (label={rec['activity_label']}, obs={rec['obs_count']}):")
        print(f"  mean_vy: {rec['mean_vy']}  abs_mean_vy: {rec['abs_mean_vy']}  std_vy: {rec['std_vy']}")
        print(f"  height_mean: {rec['height_mean']}  height_std: {rec['height_std']}  norm_height_std: {rec['norm_height_std']}")
        print(f"  ar_mean: {rec['aspect_ratio_mean']}  ar_std: {rec['aspect_ratio_std']}  ar_change: {rec['aspect_ratio_change']}")
        print(f"  dominant_frac: {rec['dominant_fraction']} ({rec['dominant_direction']})  raw_stair_fires: {rec['raw_stair_fires']}")
        known_analysis[tid] = rec

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Population-Level Distribution Analysis
    # ──────────────────────────────────────────────────────────────────────────
    groups = {
        'CURRENT_STAIR_CLASSIFIER_POSITIVES': [],
        'walking_downstairs': [],
        'running': [],
        'other': [],
    }

    for tid, r in feature_records.items():
        lbl = r['activity_label']
        if lbl == 'walking_upstairs':
            groups['CURRENT_STAIR_CLASSIFIER_POSITIVES'].append(r)
        elif lbl == 'walking_downstairs':
            groups['walking_downstairs'].append(r)
        elif lbl == 'running':
            groups['running'].append(r)
        else:
            groups['other'].append(r)

    print("\n=== STEP 4: POPULATION DISTRIBUTION COMPARISON ===")
    dist_stats = {}
    for gname, glist in groups.items():
        if not glist:
            continue
        h_stds = [x['height_std'] for x in glist]
        norm_h_stds = [x['norm_height_std'] for x in glist]
        ar_stds = [x['aspect_ratio_std'] for x in glist]
        dom_fracs = [x['dominant_fraction'] for x in glist]
        speeds = [x['mean_speed'] for x in glist]
        durations = [x['duration_s'] for x in glist]

        dist_stats[gname] = {
            'count': len(glist),
            'height_std': {'mean': round(float(np.mean(h_stds)), 4), 'median': round(float(np.median(h_stds)), 4), 'p25': round(float(np.percentile(h_stds, 25)), 4), 'p75': round(float(np.percentile(h_stds, 75)), 4)},
            'norm_height_std': {'mean': round(float(np.mean(norm_h_stds)), 4), 'median': round(float(np.median(norm_h_stds)), 4), 'p25': round(float(np.percentile(norm_h_stds, 25)), 4), 'p75': round(float(np.percentile(norm_h_stds, 75)), 4)},
            'aspect_ratio_std': {'mean': round(float(np.mean(ar_stds)), 4), 'median': round(float(np.median(ar_stds)), 4), 'p25': round(float(np.percentile(ar_stds, 25)), 4), 'p75': round(float(np.percentile(ar_stds, 75)), 4)},
            'dominant_fraction': {'mean': round(float(np.mean(dom_fracs)), 4), 'median': round(float(np.median(dom_fracs)), 4)},
            'mean_speed': {'mean': round(float(np.mean(speeds)), 4), 'median': round(float(np.median(speeds)), 4)},
            'duration_s': {'mean': round(float(np.mean(durations)), 2), 'median': round(float(np.median(durations)), 2)},
        }
        print(f"Group {gname} (N={len(glist)}):")
        print(f"  height_std:      mean={dist_stats[gname]['height_std']['mean']}  median={dist_stats[gname]['height_std']['median']}  IQR=[{dist_stats[gname]['height_std']['p25']}, {dist_stats[gname]['height_std']['p75']}]")
        print(f"  norm_height_std: mean={dist_stats[gname]['norm_height_std']['mean']}  median={dist_stats[gname]['norm_height_std']['median']}  IQR=[{dist_stats[gname]['norm_height_std']['p25']}, {dist_stats[gname]['norm_height_std']['p75']}]")
        print(f"  ar_std:          mean={dist_stats[gname]['aspect_ratio_std']['mean']}  median={dist_stats[gname]['aspect_ratio_std']['median']}  IQR=[{dist_stats[gname]['aspect_ratio_std']['p25']}, {dist_stats[gname]['aspect_ratio_std']['p75']}]")
        print(f"  dominant_frac:   mean={dist_stats[gname]['dominant_fraction']['mean']}  median={dist_stats[gname]['dominant_fraction']['median']}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 5: Offline Gate Experiment
    # ──────────────────────────────────────────────────────────────────────────
    # We test four candidate posture gates derived from the distribution analysis:
    # Candidate A: raw stair trigger AND norm_height_std >= THRESHOLD
    # Candidate B: raw stair trigger AND aspect_ratio_std >= THRESHOLD
    # Candidate C: raw stair trigger AND dominant_fraction >= THRESHOLD (temporal consistency)
    # Candidate D: raw stair trigger AND (norm_height_std >= 0.08 OR ar_std >= 0.05) AND dominant_fraction >= 0.70

    candidates_def = [
        # Candidate A variants
        ('Candidate A1 (norm_h_std >= 0.05)', lambda r: r['raw_stair_fires'] and r['norm_height_std'] >= 0.05),
        ('Candidate A2 (norm_h_std >= 0.08)', lambda r: r['raw_stair_fires'] and r['norm_height_std'] >= 0.08),
        ('Candidate A3 (norm_h_std >= 0.10)', lambda r: r['raw_stair_fires'] and r['norm_height_std'] >= 0.10),
        # Candidate B variants
        ('Candidate B1 (ar_std >= 0.03)', lambda r: r['raw_stair_fires'] and r['aspect_ratio_std'] >= 0.03),
        ('Candidate B2 (ar_std >= 0.05)', lambda r: r['raw_stair_fires'] and r['aspect_ratio_std'] >= 0.05),
        ('Candidate B3 (ar_std >= 0.08)', lambda r: r['raw_stair_fires'] and r['aspect_ratio_std'] >= 0.08),
        # Candidate C variants (Temporal Consistency)
        ('Candidate C1 (dominant_frac >= 0.65)', lambda r: r['raw_stair_fires'] and r['dominant_fraction'] >= 0.65),
        ('Candidate C2 (dominant_frac >= 0.75)', lambda r: r['raw_stair_fires'] and r['dominant_fraction'] >= 0.75),
        ('Candidate C3 (dominant_frac >= 0.85)', lambda r: r['raw_stair_fires'] and r['dominant_fraction'] >= 0.85),
        # Candidate D (Combined Compound Gate)
        ('Candidate D1 (norm_h_std >= 0.08 AND dom_frac >= 0.70)', lambda r: r['raw_stair_fires'] and r['norm_height_std'] >= 0.08 and r['dominant_fraction'] >= 0.70),
        ('Candidate D2 (norm_h_std >= 0.10 AND dom_frac >= 0.75)', lambda r: r['raw_stair_fires'] and r['norm_height_std'] >= 0.10 and r['dominant_fraction'] >= 0.75),
    ]

    print("\n=== STEP 5: OFFLINE GATE EVALUATION ===")
    gate_results = {}
    raw_stair_total = sum(1 for r in feature_records.values() if r['raw_stair_fires'])
    raw_upstairs = len(groups['CURRENT_STAIR_CLASSIFIER_POSITIVES'])
    raw_downstairs = len(groups['walking_downstairs'])

    print(f"Baseline Stair Positives: total={raw_stair_total} (upstairs={raw_upstairs}, downstairs={raw_downstairs})")

    for cname, cfunc in candidates_def:
        passed_tracks = [r for r in feature_records.values() if cfunc(r)]
        passed_up = [r for r in passed_tracks if r['dominant_direction'] == 'up']
        passed_down = [r for r in passed_tracks if r['dominant_direction'] == 'down']

        surviving_known = [tid for tid in TARGET_TRACKS if tid in [r['track_id'] for r in passed_tracks]]
        rejected_known = [tid for tid in TARGET_TRACKS if tid in feature_records and tid not in surviving_known]

        reduction_pct = round(100.0 * (1.0 - len(passed_tracks) / max(raw_stair_total, 1)), 1)

        gate_results[cname] = {
            'total_stair_positives': len(passed_tracks),
            'upstairs_positives': len(passed_up),
            'downstairs_positives': len(passed_down),
            'reduction_pct': reduction_pct,
            'surviving_known_tracks': surviving_known,
            'rejected_known_tracks': rejected_known,
            'passed_track_ids': [r['track_id'] for r in passed_tracks],
        }

        print(f"\n{cname}:")
        print(f"  total stairs: {len(passed_tracks)} (up={len(passed_up)}, down={len(passed_down)}) -> reduction: {reduction_pct}%")
        print(f"  known false positives surviving: {surviving_known}")
        print(f"  known false positives rejected:  {rejected_known}")

    final_payload = {
        'phase': '6E.4',
        'baseline_commit': 'ada5efc',
        'total_confirmed_person_tracks_ge_5': len(person_tracks),
        'known_track_analysis': known_analysis,
        'group_distribution_statistics': dist_stats,
        'offline_gate_experiments': gate_results,
        'raw_feature_records': feature_records,
    }

    with open(OUT_JSON, 'w') as f:
        json.dump(final_payload, f, indent=2, default=str)
    print(f"\nSaved diagnostic to {OUT_JSON}")
    shutil.rmtree(str(tmpdir), ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(run())
