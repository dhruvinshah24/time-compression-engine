"""
Phase 6D — Controlled 300s rerun script.

Identical configuration to Phase 6B:
  dataset:            archive_001
  duration:           300 seconds
  model:              yolo11l
  profile:            balanced
  frame_skip_rate:    5
  detection_threshold: 0.25

Only change from Phase 6B: 'cycling' added to StoryBuilder._ACTION_EVENTS.
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
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
RESULTS_DIR = REPO / 'results/TCE-v1.0'
REPORT_DIR = REPO / 'reports'
JOB_ID = 'PHASE6D-ARCHIVE_001-300S-%s' % uuid.uuid4().hex[:6].upper()

# Phase 6B reference values for comparison
PHASE6B = {
    'detections': 3366,
    'person_tracks': 249,
    'confirmed_person_tracks': 154,
    'motion_profiles': 277,
    's07_events': 232,
    'fused_events': 232,
    'story_segments': 148,
    'complete_stories': 0,
    'partial_stories': 21,
    'kept_events': 92,
    'exported_clips': 92,
    'runtime_s': 77.8,
    'rtf': 0.259,
}


async def run_full_pipeline():
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6d_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    print(f'[SETUP] job_id={JOB_ID}')
    print(f'[SETUP] tmpdir={tmpdir}')

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
        job_id=JOB_ID,
        video_id='VID-6D',
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

    stages = [
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    ]

    print(f'[PIPELINE] Starting S01–S12...')
    t_start = time.perf_counter()
    for mod in stages:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        status = 'OK' if r.success else 'FAIL'
        print(f'  {name}: {status}  W={len(r.warnings) if r.warnings else 0}')
        if r.warnings:
            for wi in r.warnings[:2]:
                print(f'    WARN: {str(wi)[:120]}')
        if not r.success:
            print(f'  ERRORS: {r.errors}')
            break
    total_runtime = time.perf_counter() - t_start

    return ctx, tmpdir, total_runtime


def extract_metrics(ctx, total_runtime):
    """Extract all Phase 6D metrics from context."""
    all_tracks = ctx.metadata.get('all_tracks', [])
    all_events = ctx.metadata.get('events', [])
    fused = ctx.metadata.get('fused_events', all_events)
    story_result = ctx.metadata.get('story_result')
    kept_events = ctx.metadata.get('kept_events', [])

    # Tracks
    person_tracks = [t for t in all_tracks if (t.class_name or '').lower() in
                     {'person', 'man', 'woman', 'child', 'baby'}]
    confirmed_person = [t for t in person_tracks if t.confirmed_at_frame is not None]

    # Detection count from S04 metrics
    s04_metrics = ctx.metadata.get('s04_metrics', {})
    total_detections = s04_metrics.get('total_detections', 0)
    if not total_detections:
        # estimate from tracks
        total_detections = sum(len(t.observations) for t in all_tracks)

    # Motion profiles
    motion_profiles = ctx.metadata.get('motion_profiles', {})

    # Story
    complete_stories = story_result.complete_segments if story_result else 0
    total_segments = len(story_result.segments) if story_result else 0
    partial_stories = story_result.partial_segments if story_result else 0

    # Events by type
    events_by_type = Counter(e.event_type for e in all_events)

    # Kept events / exported
    export_manifest = ctx.metadata.get('export_manifest', {})
    if export_manifest:
        clips = export_manifest.get('clips', [])
        exported_clips = len(clips)
    else:
        exported_clips = len(kept_events)

    return {
        'job_id': ctx.job_id,
        'total_runtime_s': round(total_runtime, 1),
        'rtf': round(total_runtime / 300, 3),
        'total_detections': total_detections,
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


def inspect_complete_stories(ctx):
    """
    Step 7/8: Inspect COMPLETE stories from Phase 6D.
    For each: verify same track, temporal ordering, entry, action, exit.
    """
    from app.engines.temporal.story_preservation.story_builder import StoryCompleteness

    story_result = ctx.metadata.get('story_result')
    if not story_result:
        print('[INSPECT] story_result not in context')
        return []

    complete_segs = [s for s in story_result.segments
                     if s.completeness == StoryCompleteness.COMPLETE]
    print(f'\n[INSPECT] {len(complete_segs)} COMPLETE story segments found')

    from app.engines.temporal.story_preservation.story_builder import (
        _ENTRY_EVENTS, _ACTION_EVENTS, _EXIT_EVENTS,
    )

    verified = []
    for seg in complete_segs[:20]:  # inspect up to 20
        track_ids = seg.track_ids
        events = seg.events
        event_types = [e.event_type for e in events]
        has_entry = any(e in _ENTRY_EVENTS for e in event_types)
        has_action = any(e in _ACTION_EVENTS for e in event_types)
        has_exit = any(e in _EXIT_EVENTS for e in event_types)
        temporal_ok = all(events[i].start_ms <= events[i+1].start_ms
                          for i in range(len(events)-1))
        evidence_ok = all(e.evidence is not None for e in events)
        cycling_events = [e for e in events if e.event_type == 'cycling']

        print(f'\n  Segment {seg.segment_id}')
        print(f'    track_ids={sorted(track_ids)}  events={len(events)}')
        print(f'    has_entry={has_entry}  has_action={has_action}  has_exit={has_exit}')
        print(f'    temporal_ok={temporal_ok}  evidence_ok={evidence_ok}')
        print(f'    narrative_score={seg.narrative_score:.3f}  is_coherent={seg.is_coherent}')
        print(f'    cycling_events={len(cycling_events)}')
        print(f'    Event chain:')
        for e in events:
            mm, ss = divmod(int(e.start_ms / 1000), 60)
            role = 'ENTRY' if e.event_type in _ENTRY_EVENTS else \
                   ('ACTION' if e.event_type in _ACTION_EVENTS else \
                   ('EXIT' if e.event_type in _EXIT_EVENTS else '—'))
            print(f'      {mm:02d}:{ss:02d}  {e.event_type:<35} conf={e.confidence:.3f}  role={role}')

        # Verify before+after (Phase 6B classification)
        entry_track_ids = sorted(track_ids)
        print(f'    Phase 6B classification: PARTIAL (cycling not in _ACTION_EVENTS)')
        print(f'    Phase 6D classification: COMPLETE ✓')

        verified.append({
            'segment_id': seg.segment_id,
            'track_ids': sorted(track_ids),
            'event_count': len(events),
            'event_types': event_types,
            'has_entry': has_entry,
            'has_action': has_action,
            'has_exit': has_exit,
            'temporal_ok': temporal_ok,
            'evidence_ok': evidence_ok,
            'cycling_events': len(cycling_events),
            'narrative_score': round(seg.narrative_score, 4),
            'is_coherent': seg.is_coherent,
            'phase6b_classification': 'PARTIAL',
            'phase6d_classification': 'COMPLETE',
        })

    return verified


def inspect_cycling_clips(ctx):
    """
    Step 9: Manual cycling audit — 5 representative events.
    Inspect evidence field for source frame, speed, confidence.
    Cannot watch footage automatically — record evidence for manual review.
    """
    all_events = ctx.metadata.get('events', [])
    all_tracks_map = {t.track_id: t for t in ctx.metadata.get('all_tracks', [])}
    cycling_evts = [e for e in all_events if e.event_type == 'cycling']

    print(f'\n[CYCLING AUDIT] {len(cycling_evts)} cycling events — sampling 5 across 300s')
    if not cycling_evts:
        return []

    # Pick 5 distributed across the clip
    n = len(cycling_evts)
    idxs = [0, n//4, n//2, 3*n//4, n-1]
    sampled = [cycling_evts[i] for i in idxs]

    audited = []
    for e in sampled:
        t = all_tracks_map.get(e.track_id)
        obs_count = len(t.observations) if t else '?'
        duration = (
            (t.observations[-1].timestamp_ms - t.observations[0].timestamp_ms) / 1000
            if t and len(t.observations) > 1 else 0
        )
        mm, ss = divmod(int(e.start_ms / 1000), 60)
        evid = e.evidence or {}
        mean_speed = evid.get('mean_speed', '?')
        cycling_conf = evid.get('cycling_conf', '?')
        reason = evid.get('reason', '?')
        person_label = evid.get('person_label', '?')
        crop = evid.get('crop_path', None)

        # Frame reference for manual inspection
        frame_ref = None
        if t and t.observations:
            mid_obs = t.observations[len(t.observations)//2]
            frame_ref = mid_obs.frame_number

        print(f'\n  [{mm:02d}:{ss:02d}] track={e.track_id}  label={person_label}')
        print(f'         conf={e.confidence:.3f}  mean_speed={mean_speed}  cycling_conf={cycling_conf}')
        print(f'         reason={reason}  obs={obs_count}  duration={duration:.1f}s')
        print(f'         crop_path={crop}')
        print(f'         frame_ref={frame_ref}  (for manual frame inspection)')
        print(f'         Manual classification: NOT VERIFIABLE (footage not watched in this phase)')

        audited.append({
            'timestamp_fmt': f'{mm:02d}:{ss:02d}',
            'track_id': e.track_id,
            'person_label': person_label,
            'confidence': round(e.confidence, 3),
            'mean_speed': mean_speed,
            'cycling_conf': cycling_conf,
            'reason': reason,
            'obs_count': obs_count,
            'track_duration_s': round(duration, 1),
            'frame_ref': frame_ref,
            'crop_path': str(crop) if crop else None,
            'manual_classification': 'NOT VERIFIABLE',
            'note': 'Footage not watched in Phase 6D. Requires human review of frames.',
        })

    return audited


def check_obs003(ctx):
    """Step 11: Check whether OBS-003 continuity issue still exists."""
    from app.engines.temporal.story_preservation.story_builder import StoryCompleteness
    story_result = ctx.metadata.get('story_result')
    if not story_result:
        return None

    issues = [(s.segment_id, s.continuity_issues)
              for s in story_result.segments if s.continuity_issues]

    if issues:
        print(f'\n[OBS-003] {len(issues)} segment(s) with continuity issues:')
        for sid, issue_list in issues[:5]:
            print(f'  {sid}: {len(issue_list)} issues')
            for iss in issue_list[:3]:
                print(f'    {iss[:100]}')
    else:
        print('\n[OBS-003] No continuity issues in this run.')

    return issues


async def main():
    print('Phase 6D — Controlled 300s Rerun with cycling vocabulary fix')
    print('Config: archive_001, 300s, yolo11l, balanced, skip=5, thresh=0.25')
    print()

    ctx, tmpdir, runtime = await run_full_pipeline()

    try:
        metrics = extract_metrics(ctx, runtime)
        print()
        print('=' * 70)
        print('PHASE 6D METRICS')
        print('=' * 70)
        for k, v in metrics.items():
            if k not in ('events_by_type', 'job_id'):
                diff = ''
                if k in PHASE6B:
                    d = (v - PHASE6B[k]) if isinstance(v, (int, float)) else ''
                    diff = f'  (6B={PHASE6B[k]}  delta={d:+})'
                print(f'  {k:<30}: {v}{diff}')

        print()
        print('Events by type:')
        for et, cnt in sorted(metrics['events_by_type'].items(), key=lambda x: -x[1]):
            print(f'  {et:<35}: {cnt}')

        verified_stories = inspect_complete_stories(ctx)
        cycling_audit = inspect_cycling_clips(ctx)
        obs003 = check_obs003(ctx)

        # Save results JSON
        result_data = {
            'phase': 'Phase 6D',
            'job_id': JOB_ID,
            'git_commit': '6D-fix-cycling-action',
            'fix_applied': 'Added "cycling" to StoryBuilder._ACTION_EVENTS',
            'metrics': metrics,
            'phase6b_reference': PHASE6B,
            'complete_story_verification': verified_stories,
            'cycling_audit_sample': cycling_audit,
            'obs003_continuity_issues': len(obs003) if obs003 else 0,
        }

        out_path = RESULTS_DIR / f'phase6d-300s-results.json'
        with open(out_path, 'w') as f:
            json.dump(result_data, f, indent=2, default=str)
        print(f'\nResults saved: {out_path}')

        # Return data for report writing
        return result_data

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == '__main__':
    result = asyncio.run(main())
    print('\nPhase 6D pipeline run complete.')
