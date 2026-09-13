"""
Phase 6D.3 — Controlled 300s experiment run.

Experimental settings:
  - require_temporal_overlap = True  (Defect A fix)
  - cycle_threshold = 0.25           (Defect B experimental threshold)

Everything else identical to Phase 6B/6D:
  archive_001, 300s, yolo11l, balanced, frame_skip=5, threshold=0.25

The experimental ActivityClassifier parameters are injected into S07
via the pipeline context settings.
"""
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
OUT   = REPO / 'results/TCE-v1.0/phase6d3-300s-results.json'

# Experimental parameters
EXP_CYCLE_THRESHOLD = 0.25
EXP_TEMPORAL_OVERLAP = True

# Phase 6D baseline for comparison (after vocabulary fix, before classifier fix)
PHASE6D_BASELINE = {
    'runtime_s': 72.6, 'rtf': 0.242,
    'total_tracks': 546, 'motion_profiles': 277,
    's07_events': 213, 'fused_events': 213,
    'story_segments': 138, 'complete_stories': 10,
    'partial_stories': 15, 'kept_events': 91, 'exported_clips': 91,
}


async def run_experiment():
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6d3_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6D3-%s' % uuid.uuid4().hex[:6].upper()
    print(f'[SETUP] job_id={job_id}  tmpdir={tmpdir}')
    print(f'[SETUP] cycle_threshold={EXP_CYCLE_THRESHOLD}  temporal_overlap={EXP_TEMPORAL_OVERLAP}')

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
        if not ret:
            break
        out.write(frame)
        i += 1
    cap.release(); out.release()
    print(f'[SETUP] Wrote {i} frames @ {fps:.1f}fps')

    ctx = PipelineContext(
        job_id=job_id,
        video_id='VID-6D3',
        video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile':              'balanced',
            'detection_model':            'yolo11l',
            'detection_confidence':       0.25,
            'detection_threshold':        0.25,
            'frame_skip_rate':            5,
            'low_light_enabled':          True,
            # Experimental ActivityClassifier parameters (Phase 6D.3)
            'cycle_threshold':            EXP_CYCLE_THRESHOLD,
            'require_temporal_overlap':   EXP_TEMPORAL_OVERLAP,
        },
    )

    stages = [
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    ]

    t_start = time.perf_counter()
    for mod in stages:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        status = 'OK' if r.success else 'FAIL'
        nw = len(r.warnings) if r.warnings else 0
        print(f'  {name}: {status}  W={nw}')
        if r.warnings:
            for wi in r.warnings[:2]:
                print(f'    WARN: {str(wi)[:120]}')
        if not r.success:
            print(f'  ERRORS: {r.errors}')
            break
    runtime = time.perf_counter() - t_start

    return ctx, tmpdir, runtime, job_id


def extract_metrics(ctx, runtime):
    from app.engines.temporal.story_preservation.story_builder import StoryCompleteness
    all_tracks = ctx.metadata.get('all_tracks', [])
    all_events = ctx.metadata.get('events', [])
    fused = ctx.metadata.get('fused_events', all_events)
    story_result = ctx.metadata.get('story_result')
    kept_events = ctx.metadata.get('kept_events', [])

    person_tracks = [t for t in all_tracks
                     if (t.class_name or '').lower() in
                     {'person', 'man', 'woman', 'child', 'baby'}]
    confirmed_person = [t for t in person_tracks if t.confirmed_at_frame is not None]

    motion_profiles = ctx.metadata.get('motion_profiles', {})
    complete_stories = story_result.complete_segments if story_result else 0
    total_segments = len(story_result.segments) if story_result else 0
    partial_stories = story_result.partial_segments if story_result else 0

    export_manifest = ctx.metadata.get('export_manifest', {})
    exported_clips = len(export_manifest.get('clips', [])) if export_manifest else len(kept_events)

    events_by_type = Counter(e.event_type for e in all_events)

    return {
        'job_id': ctx.job_id,
        'runtime_s': round(runtime, 1),
        'rtf': round(runtime / 300, 3),
        'total_tracks': len(all_tracks),
        'person_tracks': len(person_tracks),
        'confirmed_person_tracks': len(confirmed_person),
        'motion_profiles': len(motion_profiles),
        's07_events': len(all_events),
        'fused_events': len(fused),
        'story_segments': total_segments,
        'complete_stories': complete_stories,
        'partial_stories': partial_stories,
        'kept_events': len(kept_events),
        'exported_clips': exported_clips,
        'events_by_type': dict(events_by_type),
    }


def inspect_cycling_events(ctx):
    """Collect cycling event data for visual audit."""
    all_events = ctx.metadata.get('events', [])
    all_tracks_map = {t.track_id: t for t in ctx.metadata.get('all_tracks', [])}
    cycling_evts = [e for e in all_events if e.event_type == 'cycling']

    print(f'\n[CYCLING] {len(cycling_evts)} cycling events in 6D.3 run')

    if not cycling_evts:
        return []

    # Sample up to 5, distributed across the clip
    n = len(cycling_evts)
    idxs = list(dict.fromkeys([0, n//4, n//2, 3*n//4, n-1]))[:5]
    sampled = [cycling_evts[i] for i in idxs]

    audit_candidates = []
    for e in sampled:
        t = all_tracks_map.get(e.track_id)
        obs_count = len(t.observations) if t else '?'
        duration = (
            (t.observations[-1].timestamp_ms - t.observations[0].timestamp_ms) / 1000
            if t and len(t.observations) > 1 else 0
        )
        mm, ss = divmod(int(e.start_ms / 1000), 60)
        evid = e.evidence or {}
        frame_ref = None
        if t and t.observations:
            frame_ref = t.observations[len(t.observations) // 2].frame_number

        print(f'  [{mm:02d}:{ss:02d}] track={e.track_id}  conf={e.confidence:.3f}'
              f'  mean_speed={evid.get("mean_speed","?")}  obs={obs_count}'
              f'  duration={duration:.1f}s  frame_ref={frame_ref}')

        audit_candidates.append({
            'track_id': e.track_id,
            'timestamp_fmt': f'{mm:02d}:{ss:02d}',
            'start_ms': e.start_ms,
            'confidence': round(e.confidence, 3),
            'mean_speed': evid.get('mean_speed'),
            'cycling_conf': evid.get('cycling_conf'),
            'obs_count': obs_count,
            'duration_s': round(duration, 1),
            'frame_ref': frame_ref,
        })

    return audit_candidates


async def main():
    print('Phase 6D.3 — Controlled 300s Experiment')
    print(f'Experimental: cycle_threshold={EXP_CYCLE_THRESHOLD}  temporal_overlap={EXP_TEMPORAL_OVERLAP}')
    print()

    ctx, tmpdir, runtime, job_id = await run_experiment()

    try:
        metrics = extract_metrics(ctx, runtime)
        print()
        print('=' * 70)
        print('PHASE 6D.3 METRICS')
        print('=' * 70)
        for k, v in metrics.items():
            if k not in ('events_by_type', 'job_id'):
                ref = PHASE6D_BASELINE.get(k)
                delta = f'  (6D={ref}  delta={v-ref:+})' if ref is not None and isinstance(v, (int, float)) else ''
                print(f'  {k:<30}: {v}{delta}')

        print('\nEvents by type:')
        for et, cnt in sorted(metrics['events_by_type'].items(), key=lambda x: -x[1]):
            print(f'  {et:<35}: {cnt}')

        audit_candidates = inspect_cycling_events(ctx)

        result = {
            'phase': 'Phase 6D.3',
            'experimental_settings': {
                'cycle_threshold': EXP_CYCLE_THRESHOLD,
                'require_temporal_overlap': EXP_TEMPORAL_OVERLAP,
            },
            'baseline_commit': 'bd9d18e',
            'metrics': metrics,
            'phase6d_reference': PHASE6D_BASELINE,
            'cycling_audit_candidates': audit_candidates,
        }
        with open(OUT, 'w') as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f'\nSaved: {OUT}')

        return result

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == '__main__':
    asyncio.run(main())
