"""
Phase 6C — Cycling Event and Story Failure Diagnostic Script.

Runs S01–S09 on archive_001 300s and collects:
  Part A: All cycling events — timestamp, track, rule, confidence, evidence
  Part D/E: Why no complete stories — traces real event chains through S09
  Part F: S07 event type → StoryBuilder category mapping
  Part G: S08→S09 event count integrity
  Part H: OBS-003 continuity issue

Does NOT modify any pipeline code.
"""
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
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
REPORT_DIR = REPO / 'reports'
RESULTS_DIR = REPO / 'results/TCE-v1.0'

# ---------------------------------------------------------------------------
# StoryBuilder constants (copied verbatim from story_builder.py)
# ---------------------------------------------------------------------------
ENTRY_EVENTS = frozenset({'person_entered_scene', 'object_appeared'})
EXIT_EVENTS  = frozenset({'person_left_scene',   'object_disappeared'})
ACTION_EVENTS = frozenset({
    'person_walking', 'person_running', 'person_standing', 'person_loitering',
    'vehicle_approaching', 'vehicle_receding', 'vehicle_stationary',
})


async def run_pipeline_to_s09():
    """Run S01-S09 on 300s archive_001 and return full context."""
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6c_audit_'))
    print(f'[SETUP] tmpdir={tmpdir}')
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')

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
        job_id='6C-AUDIT-%s' % uuid.uuid4().hex[:6].upper(),
        video_id='VID-6C',
        video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile': 'balanced',
            'detection_model': 'yolo11l',
            'detection_confidence': 0.25,
            'detection_threshold': 0.25,
            'frame_skip_rate': 5,
            'low_light_enabled': True,
        },
    )

    stages = [
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build,
    ]

    print('[PIPELINE] Running S01–S09...')
    for mod in stages:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        status = 'OK' if r.success else 'FAIL'
        w_count = len(r.warnings) if r.warnings else 0
        print(f'  {name}: {status}  W={w_count}')
        if r.warnings:
            for wi in r.warnings[:2]:
                print(f'    WARN: {str(wi)[:100]}')
        if not r.success:
            print(f'  ERRORS: {r.errors}')
            break

    return ctx, tmpdir


def audit_cycling_events(ctx):
    """
    Part A: Inspect all cycling events from S07.
    Returns list of cycling event dicts.
    """
    all_events = ctx.metadata.get('events', [])
    cycling_evts = [e for e in all_events if e.event_type == 'cycling']
    all_tracks_map = {t.track_id: t for t in ctx.metadata.get('all_tracks', [])}

    print()
    print('=' * 70)
    print('PART A — CYCLING EVENT AUDIT')
    print('=' * 70)
    print(f'Total cycling events: {len(cycling_evts)}')
    print(f'Total S07 events:     {len(all_events)}')
    print(f'Cycling share:        {100*len(cycling_evts)/max(len(all_events),1):.1f}%')
    print()

    # Unique rule_names for cycling events
    rule_names = Counter(e.rule_name for e in cycling_evts)
    print('Cycling events by rule_name:')
    for rn, cnt in sorted(rule_names.items(), key=lambda x: -x[1]):
        print(f'  {rn}: {cnt}')

    # Unique track_ids
    track_ids = Counter(e.track_id for e in cycling_evts)
    print(f'\nCycling events by track_id ({len(track_ids)} unique tracks):')
    for tid, cnt in sorted(track_ids.items(), key=lambda x: -x[1])[:10]:
        t = all_tracks_map.get(tid)
        obs_count = len(t.observations) if t else '?'
        duration = (
            (t.observations[-1].timestamp_ms - t.observations[0].timestamp_ms) / 1000
            if t and len(t.observations) > 1 else 0
        )
        print(f'  track={tid}: {cnt} events  obs={obs_count}  duration={duration:.1f}s')

    # Confidence distribution
    confs = [e.confidence for e in cycling_evts]
    print(f'\nCycling confidence stats:')
    import numpy as np
    if confs:
        print(f'  min={min(confs):.3f}  max={max(confs):.3f}  mean={np.mean(confs):.3f}')
        bins = {'0.0–0.5': 0, '0.5–0.65': 0, '0.65–0.75': 0, '0.75+': 0}
        for c in confs:
            if c < 0.5: bins['0.0–0.5'] += 1
            elif c < 0.65: bins['0.5–0.65'] += 1
            elif c < 0.75: bins['0.65–0.75'] += 1
            else: bins['0.75+'] += 1
        for b, cnt in bins.items():
            print(f'  {b}: {cnt}')

    # Temporal distribution — 5 buckets across 300s
    print('\nCycling events across 300s (temporal distribution):')
    duration_s = 300
    bucket_size = duration_s / 5
    buckets = defaultdict(int)
    for e in cycling_evts:
        bucket = int(e.start_ms / 1000 / bucket_size)
        bucket = min(bucket, 4)
        buckets[bucket] += 1
    labels = ['0–60s', '60–120s', '120–180s', '180–240s', '240–300s']
    for i, lbl in enumerate(labels):
        print(f'  {lbl}: {buckets[i]}')

    # Evidence inspection (sample of 20 distributed events)
    n_sample = min(20, len(cycling_evts))
    step = max(1, len(cycling_evts) // n_sample)
    sampled = [cycling_evts[i] for i in range(0, len(cycling_evts), step)][:n_sample]

    print(f'\nSampled {len(sampled)} cycling events for detailed inspection:')
    sampled_data = []
    for e in sampled:
        t = all_tracks_map.get(e.track_id)
        obs_count = len(t.observations) if t else 0
        duration = (
            (t.observations[-1].timestamp_ms - t.observations[0].timestamp_ms) / 1000
            if t and len(t.observations) > 1 else 0
        )
        ts = int(e.start_ms / 1000)
        mm, ss = divmod(ts, 60)
        # Extract evidence details
        evid = e.evidence or {}
        reason = evid.get('reason', evid.get('description', '?'))
        cycling_conf = evid.get('cycling_conf', evid.get('confidence', '?'))
        mean_speed = evid.get('mean_speed', '?')
        bicycle_nearby = evid.get('bicycle_proximity', 'N/A')
        person_label = evid.get('person_label', '?')

        print(f'  [{mm:02d}:{ss:02d}] track={e.track_id}  label={person_label}  conf={e.confidence:.3f}')
        print(f'         rule={e.rule_name}  reason={reason}')
        print(f'         mean_speed={mean_speed}  cycling_conf_score={cycling_conf}')
        print(f'         track_obs={obs_count}  track_duration={duration:.1f}s')

        sampled_data.append({
            'event_id': e.event_id,
            'timestamp_s': round(e.start_ms / 1000, 1),
            'timestamp_fmt': f'{mm:02d}:{ss:02d}',
            'track_id': e.track_id,
            'person_label': person_label,
            'confidence': round(e.confidence, 3),
            'rule_name': e.rule_name,
            'reason': str(reason),
            'mean_speed': mean_speed,
            'cycling_conf_score': cycling_conf,
            'track_obs_count': obs_count,
            'track_duration_s': round(duration, 1),
            'evidence': evid,
        })

    return cycling_evts, sampled_data


def audit_story_failure(ctx):
    """
    Part D/E/F/G/H: Why does S09 produce 0 complete stories?
    """
    all_events = ctx.metadata.get('events', [])
    fused_events = ctx.metadata.get('fused_events', all_events)  # S08 output
    story_result = ctx.metadata.get('story_result')
    all_tracks_map = {t.track_id: t for t in ctx.metadata.get('all_tracks', [])}

    print()
    print('=' * 70)
    print('PART D — STORY FAILURE INVESTIGATION')
    print('=' * 70)

    # F: Event type → StoryBuilder category mapping
    print('\nPart F: S07 Event Type → StoryBuilder Category Mapping')
    print('-' * 60)
    all_event_types = Counter(e.event_type for e in all_events)
    print('Event type           | ENTRY? | ACTION? | EXIT? | Count')
    print('-' * 60)
    for et, count in sorted(all_event_types.items(), key=lambda x: -x[1]):
        is_entry = 'YES' if et in ENTRY_EVENTS else 'NO'
        is_action = 'YES' if et in ACTION_EVENTS else 'NO'
        is_exit = 'YES' if et in EXIT_EVENTS else 'NO'
        any_role = 'YES' in (is_entry, is_action, is_exit)
        marker = '' if any_role else ' ← UNROLED'
        print(f'  {et:<30} {is_entry:<6} {is_action:<7} {is_exit:<5} {count}{marker}')

    # G: S08 → S09 event count integrity
    print()
    print('Part G: S08→S09 Event Count Integrity')
    print('-' * 60)
    s08_count = len(all_events)  # S07 output = S08 input
    # S08 just attaches confidence scores; same events flow to S09
    print(f'  S07 output (= S08 input):  {s08_count}')
    if story_result:
        s09_covered = story_result.total_events_covered
        print(f'  S09 events covered:        {s09_covered}')
        if s09_covered < s08_count:
            print(f'  EVENT LOSS: {s08_count - s09_covered} events not in any story segment')
        else:
            print(f'  No event loss — all events covered by story segments')

    # E: Per-track event chains
    print()
    print('Part E: Real Candidate Story Chains')
    print('-' * 60)

    # Group events by track_id
    track_events = defaultdict(list)
    for e in all_events:
        track_events[e.track_id].append(e)

    # Sort each track's events by time
    for tid in track_events:
        track_events[tid].sort(key=lambda e: e.start_ms)

    # Classify completeness as StoryBuilder would
    def classify_completeness(events):
        types = {e.event_type for e in events}
        has_entry = bool(types & ENTRY_EVENTS)
        has_exit = bool(types & EXIT_EVENTS)
        has_action = bool(types & ACTION_EVENTS)
        if has_entry and has_exit and has_action:
            return 'COMPLETE', has_entry, has_action, has_exit
        elif has_entry and has_exit and not has_action:
            return 'PARTIAL (entry+exit, no action)', has_entry, has_action, has_exit
        elif has_entry and not has_exit:
            return 'ENTRY_ONLY', has_entry, has_action, has_exit
        elif has_exit and not has_entry:
            return 'EXIT_ONLY', has_entry, has_action, has_exit
        elif len(events) == 1:
            return 'MINIMAL', has_entry, has_action, has_exit
        else:
            return 'PARTIAL', has_entry, has_action, has_exit

    # Find top 10 tracks with most events
    candidates = sorted(track_events.items(), key=lambda x: -len(x[1]))[:15]
    print(f'\nTop candidate tracks (by event count):')
    chain_data = []
    for tid, tevents in candidates:
        completeness, has_entry, has_action, has_exit = classify_completeness(tevents)
        t = all_tracks_map.get(tid)
        obs = len(t.observations) if t else '?'
        duration_t = (
            (t.observations[-1].timestamp_ms - t.observations[0].timestamp_ms) / 1000
            if t and len(t.observations) > 1 else 0
        )
        print(f'\n  Track {tid} (obs={obs}, duration={duration_t:.1f}s):')
        print(f'    Completeness: {completeness}')
        print(f'    has_entry={has_entry}  has_action={has_action}  has_exit={has_exit}')
        print(f'    Events ({len(tevents)}):')

        chain = []
        for e in tevents:
            mm, ss = divmod(int(e.start_ms / 1000), 60)
            is_entry = e.event_type in ENTRY_EVENTS
            is_action = e.event_type in ACTION_EVENTS
            is_exit = e.event_type in EXIT_EVENTS
            role = 'ENTRY' if is_entry else ('ACTION' if is_action else ('EXIT' if is_exit else '—'))
            print(f'      {mm:02d}:{ss:02d}  {e.event_type:<35} conf={e.confidence:.3f}  role={role}  rule={e.rule_name}')
            chain.append({
                'timestamp_s': round(e.start_ms / 1000, 1),
                'event_type': e.event_type,
                'confidence': round(e.confidence, 3),
                'role_in_story': role,
                'rule_name': e.rule_name,
            })

        # Diagnose why NOT complete
        missing = []
        if not has_entry: missing.append('entry event (person_entered_scene)')
        if not has_action: missing.append('action event (' + ', '.join(sorted(ACTION_EVENTS)) + ')')
        if not has_exit: missing.append('exit event (person_left_scene)')

        if completeness != 'COMPLETE' and missing:
            print(f'    WHY NOT COMPLETE: Missing — {"; ".join(missing)}')

        # Check if cycling events are present (and note they are NOT in _ACTION_EVENTS)
        has_cycling = any(e.event_type == 'cycling' for e in tevents)
        if has_cycling and not has_action:
            cycling_count = sum(1 for e in tevents if e.event_type == 'cycling')
            print(f'    NOTE: {cycling_count} cycling event(s) exist but "cycling" is NOT in StoryBuilder _ACTION_EVENTS')
            print(f'          If cycling were an action, this track would be COMPLETE.')

        chain_data.append({
            'track_id': tid,
            'obs_count': obs,
            'duration_s': round(duration_t, 1),
            'event_count': len(tevents),
            'completeness': completeness,
            'has_entry': has_entry,
            'has_action': has_action,
            'has_exit': has_exit,
            'has_cycling': has_cycling,
            'would_be_complete_if_cycling_counted': (
                has_cycling and has_entry and has_exit and not has_action
            ),
            'events': chain,
        })

    # Count: how many tracks would be COMPLETE if cycling were an action?
    would_complete = sum(
        1 for d in chain_data
        if d.get('would_be_complete_if_cycling_counted', False)
    )
    total_unique_tracks = len(track_events)
    print()
    print(f'Summary:')
    print(f'  Total story tracks (unique track IDs): {total_unique_tracks}')
    print(f'  Tracks that WOULD be COMPLETE if cycling counted as action: {would_complete}')

    # Global count across all tracks
    total_would_complete = sum(
        1 for tid, tevents in track_events.items()
        if (
            any(e.event_type in ENTRY_EVENTS for e in tevents)
            and any(e.event_type in EXIT_EVENTS for e in tevents)
            and any(e.event_type == 'cycling' for e in tevents)
            and not any(e.event_type in ACTION_EVENTS for e in tevents)
        )
    )
    print(f'  Globally (all {total_unique_tracks} tracks): {total_would_complete} would be COMPLETE')

    # H: OBS-003 — continuity issue
    print()
    print('Part H: OBS-003 — S09 Continuity Issue')
    print('-' * 60)
    if story_result:
        for seg in story_result.segments:
            if seg.continuity_issues:
                print(f'  Segment {seg.segment_id}:')
                print(f'    track_ids: {seg.track_ids}')
                print(f'    event_count: {seg.event_count}')
                print(f'    completeness: {seg.completeness}')
                print(f'    is_coherent: {seg.is_coherent}')
                print(f'    continuity_issues: {seg.continuity_issues}')
                print(f'    continuity_warnings: {seg.continuity_warnings}')
                print(f'    events:')
                for e in seg.events:
                    mm, ss = divmod(int(e.start_ms / 1000), 60)
                    print(f'      {mm:02d}:{ss:02d} {e.event_type} conf={e.confidence:.3f}')
    else:
        print('  story_result not in context — cannot inspect')

    return chain_data, track_events


def build_reports(cycling_evts, sampled_data, chain_data, track_events, ctx):
    """Write all Phase 6C reports."""
    all_events = ctx.metadata.get('events', [])
    all_tracks_map = {t.track_id: t for t in ctx.metadata.get('all_tracks', [])}
    story_result = ctx.metadata.get('story_result')

    # ── cycling-event-audit-archive001-300s.json ──────────────────────────────
    cycling_json = {
        'phase': 'Phase 6C',
        'dataset': 'archive_001',
        'clip_s': 300,
        'total_cycling_events': len(cycling_evts),
        'total_s07_events': len(all_events),
        'cycling_share_pct': round(100 * len(cycling_evts) / max(len(all_events), 1), 1),
        'cycling_by_rule': dict(Counter(e.rule_name for e in cycling_evts)),
        'cycling_by_track': dict(Counter(e.track_id for e in cycling_evts)),
        'confidence_stats': {
            'min': min((e.confidence for e in cycling_evts), default=0),
            'max': max((e.confidence for e in cycling_evts), default=0),
        },
        'sampled_events': sampled_data,
    }
    path = REPORT_DIR / 'cycling-event-audit-archive001-300s.json'
    with open(path, 'w') as f:
        json.dump(cycling_json, f, indent=2, default=str)
    print(f'\nWrote: {path}')

    # ── story-candidate-chains-archive001-300s.json ───────────────────────────
    # Count global would-be-complete
    total_would_complete = sum(
        1 for tid, tevents in track_events.items()
        if (
            any(e.event_type in ENTRY_EVENTS for e in tevents)
            and any(e.event_type in EXIT_EVENTS for e in tevents)
            and any(e.event_type == 'cycling' for e in tevents)
            and not any(e.event_type in ACTION_EVENTS for e in tevents)
        )
    )
    story_json = {
        'phase': 'Phase 6C',
        'dataset': 'archive_001',
        'clip_s': 300,
        'total_story_tracks': len(track_events),
        'tracks_would_complete_if_cycling_action': total_would_complete,
        'action_events_set': sorted(ACTION_EVENTS),
        'note': '"cycling" is NOT in StoryBuilder _ACTION_EVENTS. Tracks with entry+cycling+exit are classified PARTIAL, not COMPLETE.',
        'candidate_chains': chain_data,
    }
    path = REPORT_DIR / 'story-candidate-chains-archive001-300s.json'
    with open(path, 'w') as f:
        json.dump(story_json, f, indent=2, default=str)
    print(f'Wrote: {path}')


async def main():
    print('Phase 6C — Diagnostic Investigation')
    print('Cycling dominance + FAIL-008 (zero complete stories)')
    print()

    ctx, tmpdir = await run_pipeline_to_s09()

    try:
        cycling_evts, sampled_data = audit_cycling_events(ctx)
        chain_data, track_events = audit_story_failure(ctx)
        build_reports(cycling_evts, sampled_data, chain_data, track_events, ctx)
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)

    print('\nPhase 6C diagnostic complete.')


if __name__ == '__main__':
    asyncio.run(main())
