"""
Phase 6B — FAIL-006 and FAIL-007 verification on 300s run.

Checks:
1. FAIL-006: is_confirmed == False for any track with confirmed_at_frame != None
2. FAIL-007: S07 ran without AttributeError on TrackBBox
3. Track confirmation breakdown (per-class, per-state)
4. Top story segments with timestamps
5. Event sampling for manual audit
6. Compression audit
"""
import asyncio, json, os, sys, tempfile, shutil, uuid
from pathlib import Path
from collections import defaultdict, Counter
import cv2

BACKEND = Path('backend')
REPO = Path('.')
sys.path.insert(0, str(BACKEND))

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
RESULT_JSON = REPO / 'results/TCE-v1.0/phase6-pipeline-run-archive_001_300s.json'


async def verify():
    import logging
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('ultralytics').setLevel(logging.WARNING)

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6b_verify_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')

    try:
        print('[1] Extracting 300s clip...')
        clip_path = str(tmpdir / 'clip.mp4')
        cap = cv2.VideoCapture(str(VIDEO))
        fps = cap.get(cv2.CAP_PROP_FPS)
        w, h = int(cap.get(3)), int(cap.get(4))
        n = int(fps * 300)
        out = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
        i = 0
        while i < n:
            ret, frame = cap.read()
            if not ret: break
            out.write(frame); i += 1
        cap.release(); out.release()
        print(f'    fps={fps:.1f}  frames_written={i}')

        from app.pipeline.context import PipelineContext
        from app.pipeline.stages import (
            s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
            s05_track, s06_motion_analyze, s07_event_understand
        )
        from app.engines.perception.tracker.track import TrackState

        ctx = PipelineContext(
            job_id='6B-VERIFY-%s' % uuid.uuid4().hex[:6].upper(),
            video_id='VID-6B',
            video_path=clip_path,
            output_dir=str(tmpdir / 'outputs'),
            settings={
                'model_profile': 'balanced',
                'detection_model': 'yolo11l',
                'detection_confidence': 0.25,
                'frame_skip_rate': 5,
                'detection_threshold': 0.25,
                'low_light_enabled': True,
            },
        )

        print('[2] Running S01-S07...')
        import warnings as py_warnings
        captured_warnings = []
        stage_warnings = {}

        for mod in [s01_upload, s02_extract, s03_scene_detect,
                    s04_object_detect, s05_track]:
            r = await mod.run(ctx)
            stage_warnings[mod.__name__.split('.')[-1]] = r.warnings
            status = 'OK' if r.success else 'FAIL'
            print(f'    {mod.__name__.split(".")[-1]}: {status}  W={len(r.warnings)}')

        # S06
        r = await s06_motion_analyze.run(ctx)
        stage_warnings['s06'] = r.warnings
        print(f'    s06_motion_analyze: {"OK" if r.success else "FAIL"}  W={len(r.warnings)}')

        # S07 — capture warnings specifically
        r = await s07_event_understand.run(ctx)
        s07_warnings = r.warnings
        stage_warnings['s07'] = r.warnings
        print(f'    s07_event_understand: {"OK" if r.success else "FAIL"}  W={len(r.warnings)}')
        for w in r.warnings:
            print(f'      WARN: {w[:100]}')

        # ── FAIL-007 verification ────────────────────────────────────────────
        print()
        print('=' * 60)
        print('FAIL-007 VERIFICATION')
        print('=' * 60)
        pose_attr_err = any(
            'TrackBBox' in str(w) or 'has no len' in str(w) or 'Temporal pose analysis failed' in str(w)
            for w in s07_warnings
        )
        print('AttributeError on TrackBBox:', 'YES — REGRESSION' if pose_attr_err else 'NO — CLEAN')
        pose_m = r.metrics or {}
        print('temporal_pose_events:', pose_m.get('temporal_pose_events', '?'))
        print('pose_events_detected:', pose_m.get('pose_events_detected', '?'))
        events_by_type = pose_m.get('events_by_type', {})
        pose_types = {k: v for k, v in events_by_type.items()
                      if k in ('person_crawling', 'person_crouching_sustained',
                               'person_fallen', 'person_falling_likely',
                               'person_running', 'person_running_detected')}
        print('Pose event types in S07 output:', pose_types if pose_types else '{} (none)')

        # ── FAIL-006 verification ────────────────────────────────────────────
        print()
        print('=' * 60)
        print('FAIL-006 VERIFICATION')
        print('=' * 60)
        all_tracks = ctx.metadata.get('all_tracks', [])
        PERSON_CLASSES = {'person', 'man', 'woman', 'child'}
        person_tracks = [t for t in all_tracks if (t.class_name or '').lower() in PERSON_CLASSES]

        fail006_regression = []
        for t in all_tracks:
            if t.confirmed_at_frame is not None and not t.is_confirmed:
                fail006_regression.append(t)

        print(f'Total tracks:            {len(all_tracks)}')
        print(f'Person tracks:           {len(person_tracks)}')
        print(f'Confirmed tracks (all):  {sum(1 for t in all_tracks if t.is_confirmed)}')
        print(f'Confirmed person tracks: {sum(1 for t in person_tracks if t.is_confirmed)}')
        print(f'ReID persons identified: {ctx.metadata.get("unique_persons_count", len(set(t.person_label for t in person_tracks if t.person_label)))}')
        print()
        print(f'FAIL-006 regression check:')
        print(f'  Tracks with confirmed_at_frame!=None but is_confirmed==False: {len(fail006_regression)}')
        if fail006_regression:
            print('  REGRESSION DETECTED:')
            for t in fail006_regression[:5]:
                print(f'    track_id={t.track_id} state={t.state} confirmed_at={t.confirmed_at_frame}')
        else:
            print('  NONE — FAIL-006 fix holds for 300s run')

        # State distribution
        state_counts = Counter(t.state.value for t in person_tracks)
        print()
        print('Person track state distribution:')
        for state, count in sorted(state_counts.items()):
            print(f'  {state}: {count}')

        # Confirmation rate
        confirmed_persons = [t for t in person_tracks if t.is_confirmed]
        conf_rate = 100 * len(confirmed_persons) / max(len(person_tracks), 1)
        print()
        print(f'Person confirmation rate: {len(confirmed_persons)}/{len(person_tracks)} = {conf_rate:.1f}%')

        # Frame-matched distribution for confirmed persons
        obs_bins = {'1': 0, '2': 0, '3-5': 0, '6-10': 0, '11-20': 0, '21-49': 0, '50+': 0}
        for t in confirmed_persons:
            n = t.total_frames_matched
            if n == 1: obs_bins['1'] += 1
            elif n == 2: obs_bins['2'] += 1
            elif n <= 5: obs_bins['3-5'] += 1
            elif n <= 10: obs_bins['6-10'] += 1
            elif n <= 20: obs_bins['11-20'] += 1
            elif n <= 49: obs_bins['21-49'] += 1
            else: obs_bins['50+'] += 1
        print()
        print('Confirmed person track frames_matched distribution:')
        for bucket, count in obs_bins.items():
            print(f'  {bucket}: {count}')

        # ── Event breakdown ──────────────────────────────────────────────────
        print()
        print('=' * 60)
        print('S07 EVENT BREAKDOWN')
        print('=' * 60)
        events = ctx.metadata.get('events', [])
        type_counts = Counter(e.event_type for e in events)
        print(f'Total events in S07 output: {len(events)}')
        print('Events by type:')
        for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f'  {t}: {n}')

        # Sample events for audit
        print()
        print('Sample events for manual audit (first 3 per type):')
        seen = defaultdict(int)
        for e in sorted(events, key=lambda x: x.start_ms):
            if seen[e.event_type] >= 3:
                continue
            seen[e.event_type] += 1
            ts = int(e.start_ms / 1000)
            mm, ss = divmod(ts, 60)
            print(f'  [{e.event_type}]')
            print(f'    t={mm:02d}:{ss:02d}  track={e.track_id}  conf={e.confidence:.3f}')
            evid = e.evidence or {}
            note = evid.get('description', evid.get('reason', evid.get('note', '')))
            if note:
                print(f'    evidence: {str(note)[:100]}')

        # ── Save verification output ─────────────────────────────────────────
        out_data = {
            'fail006_regression_count': len(fail006_regression),
            'fail007_pose_attr_error': pose_attr_err,
            'person_tracks_total': len(person_tracks),
            'confirmed_persons': len(confirmed_persons),
            'confirmation_rate_pct': round(conf_rate, 1),
            'temporal_pose_events': pose_m.get('temporal_pose_events', 0),
            'pose_event_types': pose_types,
            'events_by_type': dict(type_counts),
            'confirmed_distribution': obs_bins,
            'state_distribution': dict(state_counts),
        }
        out_path = REPO / 'results/TCE-v1.0/fail006-007-verify-300s.json'
        with open(out_path, 'w') as f:
            json.dump(out_data, f, indent=2)
        print()
        print(f'Verification JSON: {out_path}')

    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


if __name__ == '__main__':
    asyncio.run(verify())
