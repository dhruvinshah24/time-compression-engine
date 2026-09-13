"""
Phase 6E.6 — Staircase Scene-Context Guard Diagnostic.

Evaluates whether YOLO-World open-vocabulary scene context can reliably
detect/reject staircase structures in archive_001 (300s) to guard
against velocity-derived stair false positives.

Tests:
- Strategy A: Stair-only query ("stairs")
- Strategy B: Expanded query ("stairs", "staircase", "steps", "escalator", "ramp", "incline")
- Strategy C: Full frame scene context vs person-expanded crop
- Temporal persistence: 1, 2, 3, 5 frames
- Spatial relationship: distance/overlap between person and detected structure
- False-positive suppression rate across all 79 raw stair triggers and known tracks (14, 177, 252, 273).
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
from collections import defaultdict
import cv2
import numpy as np

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
OUT_JSON = REPO / 'results/TCE-v1.0/phase6e6-stair-scene-context.json'
YOLO_WORLD_WEIGHTS = BACKEND / 'yolov8l-worldv2.pt'

TARGET_TRACKS = [14, 56, 160, 177, 252, 273]

STRATEGY_A_CLASSES = ["stairs"]
STRATEGY_B_CLASSES = ["stairs", "staircase", "steps", "escalator", "ramp", "incline"]


async def run():
    from ultralytics import YOLO
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect, s05_track,
    )
    from app.utils.activity_classifier import (
        ActivityClassifier,
        WALK_THRESHOLD,
        RUN_THRESHOLD,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6e6_diag_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6E6-%s' % uuid.uuid4().hex[:6].upper()
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
        job_id=job_id, video_id='VID-6E6-DIAG', video_path=clip_path,
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
        and len(t.observations) >= 5
    ]
    print(f'\nTotal confirmed person tracks (obs >= 5): {len(person_tracks)}')

    clf = ActivityClassifier(
        fps=fps, frame_skip=5,
        cycle_threshold=0.25, require_temporal_overlap=True,
        min_activity_observations=5,
    )

    # 1. Identify all stair-positive tracks
    stair_positive_tracks = []
    track_metadata = {}
    for track in person_tracks:
        tid = track.track_id
        obs = track.observations
        act_res = clf.classify(track, all_tracks=all_tracks)

        centers = []
        for o in obs:
            b = o.bbox
            if b is not None:
                from app.engines.perception.tracker.track import TrackBBox
                if isinstance(b, TrackBBox):
                    cx = (b.x1 + b.x2) / 2.0; cy = (b.y1 + b.y2) / 2.0
                elif hasattr(b, '__len__') and len(b) >= 4:
                    cx = (b[0] + b[2]) / 2.0; cy = (b[1] + b[3]) / 2.0
                else: continue
                if any(v > 1.5 for v in [cx, cy]):
                    cx /= max(w, 1.0); cy /= max(h, 1.0)
                centers.append((cx, cy))

        vy_arr = np.array([
            (centers[i][1] - centers[i-1][1]) / dt
            for i in range(1, len(centers))
        ]) if len(centers) >= 2 else np.array([])

        mean_speed = act_res.evidence.get('mean_speed', 0.0)
        raw_stair_conf, raw_stair_dir = clf._detect_stairs(vy_arr, mean_speed)
        raw_stair_fires = (raw_stair_conf >= 0.55 and mean_speed >= WALK_THRESHOLD)

        meta = {
            'track_id': tid,
            'obs_count': len(obs),
            'start_frame': obs[0].frame_number,
            'end_frame': obs[-1].frame_number,
            'start_ms': obs[0].timestamp_ms,
            'end_ms': obs[-1].timestamp_ms,
            'raw_stair_fires': raw_stair_fires,
            'raw_stair_conf': round(raw_stair_conf, 3),
            'raw_stair_dir': raw_stair_dir,
            'activity_label': act_res.label,
        }
        track_metadata[tid] = meta
        if raw_stair_fires or tid in TARGET_TRACKS:
            stair_positive_tracks.append(track)

    raw_stair_count = sum(1 for m in track_metadata.values() if m['raw_stair_fires'])
    print(f'Total raw stair-positive tracks: {raw_stair_count}')

    # 2. Gather unique frames to inspect
    # Sample every observation frame for target tracks + representative sample across all stair tracks
    frame_to_tracks = defaultdict(list)
    for track in stair_positive_tracks:
        for o in track.observations:
            frame_to_tracks[o.frame_number].append((track.track_id, o))

    unique_frames = sorted(frame_to_tracks.keys())
    print(f'Total unique track observation frames to audit: {len(unique_frames)}')

    # Extract all required frames from video
    cap = cv2.VideoCapture(clip_path)
    loaded_frames = {}
    curr_fn = 0
    ret = True
    target_set = set(unique_frames)
    max_target = max(target_set) if target_set else 0

    while ret and curr_fn <= max_target:
        ret, frame = cap.read()
        if not ret: break
        if curr_fn in target_set:
            loaded_frames[curr_fn] = frame
        curr_fn += 1
    cap.release()
    print(f'Loaded {len(loaded_frames)} video frames into memory')

    # 3. Load YOLO-World model
    print(f'\n[YOLO-World] Loading weights from {YOLO_WORLD_WEIGHTS}...')
    world_model = YOLO(str(YOLO_WORLD_WEIGHTS))

    # Test Strategy A: "stairs" only
    print('[Strategy A] Setting classes: ["stairs"]')
    world_model.set_classes(STRATEGY_A_CLASSES)
    strat_a_detections = {}

    batch_size = 32
    frame_list = [(fn, loaded_frames[fn]) for fn in unique_frames if fn in loaded_frames]

    print(f'Running Strategy A inference across {len(frame_list)} frames...')
    for b_idx in range(0, len(frame_list), batch_size):
        batch = frame_list[b_idx : b_idx + batch_size]
        fns = [x[0] for x in batch]
        imgs = [x[1] for x in batch]
        results = world_model.predict(imgs, conf=0.10, verbose=False, device=0)
        for fn, r in zip(fns, results):
            dets = []
            if r.boxes is not None and len(r.boxes) > 0:
                for b in r.boxes:
                    cls_id = int(b.cls[0].item())
                    conf = float(b.conf[0].item())
                    cls_name = r.names.get(cls_id, str(cls_id))
                    xyxy = b.xyxy[0].tolist()
                    dets.append({
                        'class_name': cls_name,
                        'confidence': round(conf, 3),
                        'bbox': [round(v, 1) for v in xyxy],
                        'bbox_norm': [round(xyxy[0]/w, 4), round(xyxy[1]/h, 4), round(xyxy[2]/w, 4), round(xyxy[3]/h, 4)],
                    })
            strat_a_detections[fn] = dets

    # Test Strategy B: Expanded query
    print('\n[Strategy B] Setting classes: ["stairs", "staircase", "steps", "escalator", "ramp", "incline"]')
    del world_model
    world_model_b = YOLO(str(YOLO_WORLD_WEIGHTS))
    world_model_b.set_classes(STRATEGY_B_CLASSES)
    strat_b_detections = {}

    print(f'Running Strategy B inference across {len(frame_list)} frames...')
    for b_idx in range(0, len(frame_list), batch_size):
        batch = frame_list[b_idx : b_idx + batch_size]
        fns = [x[0] for x in batch]
        imgs = [x[1] for x in batch]
        results = world_model_b.predict(imgs, conf=0.10, verbose=False, device=0)
        for fn, r in zip(fns, results):
            dets = []
            if r.boxes is not None and len(r.boxes) > 0:
                for b in r.boxes:
                    cls_id = int(b.cls[0].item())
                    conf = float(b.conf[0].item())
                    cls_name = r.names.get(cls_id, str(cls_id))
                    xyxy = b.xyxy[0].tolist()
                    dets.append({
                        'class_name': cls_name,
                        'confidence': round(conf, 3),
                        'bbox': [round(v, 1) for v in xyxy],
                        'bbox_norm': [round(xyxy[0]/w, 4), round(xyxy[1]/h, 4), round(xyxy[2]/w, 4), round(xyxy[3]/h, 4)],
                    })
            strat_b_detections[fn] = dets

    # 4. Helper for spatial relationship
    def compute_spatial_rel(p_bbox, s_bbox):
        # p_bbox, s_bbox normalized [x1, y1, x2, y2]
        px1, py1, px2, py2 = p_bbox
        sx1, sy1, sx2, sy2 = s_bbox
        # IoU
        ix1 = max(px1, sx1); iy1 = max(py1, sy1)
        ix2 = min(px2, sx2); iy2 = min(py2, sy2)
        iw = max(0.0, ix2 - ix1); ih = max(0.0, iy2 - iy1)
        inter = iw * ih
        p_area = max(0.0, (px2 - px1) * (py2 - py1))
        s_area = max(0.0, (sx2 - sx1) * (sy2 - sy1))
        union = p_area + s_area - inter
        iou = inter / max(union, 1e-6)

        # Centroid distance
        pcx = (px1 + px2) / 2.0; pcy = (py1 + py2) / 2.0
        scx = (sx1 + sx2) / 2.0; scy = (sy1 + sy2) / 2.0
        dist = float(np.sqrt((pcx - scx)**2 + (pcy - scy)**2))
        return round(iou, 4), round(dist, 4)

    # 5. Analyze per-track scene context evidence
    def analyze_track_context(track, detections_by_frame, min_conf=0.15):
        obs = track.observations
        total_obs = len(obs)
        frames_with_det = []
        all_dets = []
        spatial_rels = []

        for o in obs:
            fn = o.frame_number
            dets = detections_by_frame.get(fn, [])
            valid = [d for d in dets if d['confidence'] >= min_conf]
            if valid:
                frames_with_det.append(fn)
                # Person bbox
                b = o.bbox
                from app.engines.perception.tracker.track import TrackBBox
                if isinstance(b, TrackBBox):
                    p_norm = [b.x1/w if b.x1>1.5 else b.x1, b.y1/h if b.y1>1.5 else b.y1,
                              b.x2/w if b.x2>1.5 else b.x2, b.y2/h if b.y2>1.5 else b.y2]
                else:
                    p_norm = [b[0]/w if b[0]>1.5 else b[0], b[1]/h if b[1]>1.5 else b[1],
                              b[2]/w if b[2]>1.5 else b[2], b[3]/h if b[3]>1.5 else b[3]]
                for vd in valid:
                    iou, dist = compute_spatial_rel(p_norm, vd['bbox_norm'])
                    spatial_rels.append({'frame': fn, 'class': vd['class_name'], 'conf': vd['confidence'], 'iou': iou, 'dist': dist})
                    all_dets.append(vd)

        persistence = len(frames_with_det)
        pct_obs = round(100.0 * persistence / max(total_obs, 1), 1)
        max_conf = max([d['confidence'] for d in all_dets]) if all_dets else 0.0
        classes_found = list(set(d['class_name'] for d in all_dets))

        return {
            'has_detection': persistence > 0,
            'persistence_frames': persistence,
            'persistence_pct': pct_obs,
            'max_confidence': max_conf,
            'classes_found': classes_found,
            'detections_count': len(all_dets),
            'spatial_relationships': spatial_rels,
        }

    # Evaluate across thresholds & persistence levels
    print('\n=== EVALUATING SCENE-CONTEXT SUPPRESSION ===')
    thresholds = [0.15, 0.20, 0.25, 0.30]
    persistence_cutoffs = [1, 2, 3, 5]

    suppression_eval = {}

    for strat_name, det_dict in [('Strategy_A (stairs only)', strat_a_detections),
                                 ('Strategy_B (expanded query)', strat_b_detections)]:
        strat_results = {}
        for conf in thresholds:
            for pers in persistence_cutoffs:
                key = f'conf>={conf:.2f}_pers>={pers}'
                retained_stair_tracks = []
                suppressed_stair_tracks = []

                for track in stair_positive_tracks:
                    tid = track.track_id
                    is_raw_stair = track_metadata[tid]['raw_stair_fires']
                    if not is_raw_stair:
                        continue
                    res = analyze_track_context(track, det_dict, min_conf=conf)
                    # If scene context supports stairs:
                    if res['persistence_frames'] >= pers:
                        retained_stair_tracks.append(tid)
                    else:
                        suppressed_stair_tracks.append(tid)

                supp_pct = round(100.0 * len(suppressed_stair_tracks) / max(raw_stair_count, 1), 1)
                strat_results[key] = {
                    'confidence_threshold': conf,
                    'min_persistence_frames': pers,
                    'retained_tracks_count': len(retained_stair_tracks),
                    'suppressed_tracks_count': len(suppressed_stair_tracks),
                    'suppression_pct': supp_pct,
                    'retained_track_ids': retained_stair_tracks,
                }
        suppression_eval[strat_name] = strat_results

    # Print summary of Strategy A & B at standard settings
    for sname, sres in suppression_eval.items():
        print(f"\n{sname}:")
        for key in ['conf>=0.15_pers>=1', 'conf>=0.15_pers>=2', 'conf>=0.20_pers>=2', 'conf>=0.25_pers>=2']:
            r = sres[key]
            print(f"  {key}: suppressed {r['suppressed_tracks_count']}/{raw_stair_count} ({r['suppression_pct']}%) — retained {r['retained_tracks_count']}")

    # 6. Detailed Known Track Audit
    print('\n=== STEP 6: KNOWN FALSE-POSITIVE AUDIT ===')
    known_audit = {}
    for tid in TARGET_TRACKS:
        t_obj = next((t for t in stair_positive_tracks if t.track_id == tid), None)
        if not t_obj:
            t_obj = next((t for t in person_tracks if t.track_id == tid), None)
        if not t_obj:
            continue

        meta = track_metadata[tid]
        ctx_a_15 = analyze_track_context(t_obj, strat_a_detections, min_conf=0.15)
        ctx_a_20 = analyze_track_context(t_obj, strat_a_detections, min_conf=0.20)
        ctx_b_15 = analyze_track_context(t_obj, strat_b_detections, min_conf=0.15)
        ctx_b_20 = analyze_track_context(t_obj, strat_b_detections, min_conf=0.20)

        known_audit[str(tid)] = {
            'track_id': tid,
            'raw_activity_label': meta['activity_label'],
            'raw_stair_fires': meta['raw_stair_fires'],
            'raw_stair_conf': meta['raw_stair_conf'],
            'raw_stair_dir': meta['raw_stair_dir'],
            'obs_count': meta['obs_count'],
            'start_frame': meta['start_frame'],
            'end_frame': meta['end_frame'],
            'strategy_a_conf15': ctx_a_15,
            'strategy_a_conf20': ctx_a_20,
            'strategy_b_conf15': ctx_b_15,
            'strategy_b_conf20': ctx_b_20,
        }
        print(f"\nTrack {tid} ({meta['activity_label']}, raw_stair={meta['raw_stair_fires']}):")
        print(f"  Strategy A (stairs): pers={ctx_a_15['persistence_frames']}/{meta['obs_count']} max_conf={ctx_a_15['max_confidence']}")
        print(f"  Strategy B (expanded): pers={ctx_b_15['persistence_frames']}/{meta['obs_count']} max_conf={ctx_b_15['max_confidence']} classes={ctx_b_15['classes_found']}")
        if ctx_b_15['spatial_relationships']:
            print(f"    Sample spatial: {ctx_b_15['spatial_relationships'][:2]}")

    # 7. False alarm analysis in the scene footage
    # Find all frames in archive_001 where YOLO-World detected "stairs", "steps", etc.
    all_strat_a_hits = [(fn, d) for fn, dets in strat_a_detections.items() for d in dets if d['confidence'] >= 0.15]
    all_strat_b_hits = [(fn, d) for fn, dets in strat_b_detections.items() for d in dets if d['confidence'] >= 0.15]

    print(f"\nTotal frame detections across entire clip:")
    print(f"  Strategy A (stairs conf >= 0.15): {len(all_strat_a_hits)} hits in {len(strat_a_detections)} frames")
    print(f"  Strategy B (expanded conf >= 0.15): {len(all_strat_b_hits)} hits in {len(strat_b_detections)} frames")

    output_payload = {
        'phase': '6E.6',
        'baseline_commit': '5898262',
        'total_confirmed_person_tracks_ge_5': len(person_tracks),
        'total_raw_stair_triggers': raw_stair_count,
        'total_audited_frames': len(unique_frames),
        'suppression_eval': suppression_eval,
        'known_audit': known_audit,
        'frame_level_hits_summary': {
            'strategy_a_hits_ge_15': len(all_strat_a_hits),
            'strategy_b_hits_ge_15': len(all_strat_b_hits),
        },
    }

    with open(OUT_JSON, 'w') as f:
        json.dump(output_payload, f, indent=2, default=str)
    print(f"\nDiagnostic results written to {OUT_JSON}")
    shutil.rmtree(str(tmpdir), ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(run())
