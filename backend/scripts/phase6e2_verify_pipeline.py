"""
Re-run S06-S12 pipeline with min_activity_observations=5 and correctly extract story segments.
"""
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.WARNING)
for ns in ('ultralytics', 'app.model_registry', 'app.utils.ffmpeg'):
    logging.getLogger(ns).setLevel(logging.ERROR)

VIDEO = REPO / 'data/real/archive/videos/WhenYouA1948_512kb.mp4'
OUT_JSON = REPO / 'results/TCE-v1.0/phase6e2-short-track-results.json'

async def run():
    import cv2
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    )

    tmpdir = Path(tempfile.mkdtemp(prefix='tce_6e2_pipe_'))
    os.environ['STORAGE_LOCAL_PATH'] = str(tmpdir / 'outputs')
    job_id = 'PHASE6E2-%s' % uuid.uuid4().hex[:6].upper()
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
        job_id=job_id, video_id='VID-6E2-PIPE', video_path=clip_path,
        output_dir=str(tmpdir / 'outputs'),
        settings={
            'model_profile': 'balanced', 'detection_model': 'yolo11l',
            'detection_confidence': 0.25, 'detection_threshold': 0.25,
            'frame_skip_rate': 5, 'low_light_enabled': True,
            'cycle_threshold': 0.25, 'require_temporal_overlap': True,
            'min_activity_observations': 5,
        },
    )

    stages = [
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    ]
    for mod in stages:
        r = await mod.run(ctx)
        name = mod.__name__.split('.')[-1]
        print(f'  {name}: {"OK" if r.success else "FAIL"}')
        if not r.success:
            print(f'  ERRORS: {r.errors}'); return

    story_result = ctx.metadata.get('story_result')
    segments = story_result.segments if story_result else []
    print(f'\nTotal story segments: {len(segments)}')

    story_completeness = Counter()
    complete_stories = []
    for s in segments:
        comp = s.completeness.value if hasattr(s.completeness, 'value') else str(s.completeness)
        story_completeness[comp] += 1
        if comp == 'complete':
            complete_stories.append({
                'segment_id': s.segment_id,
                'track_ids': list(s.track_ids),
                'event_types': [e.event_type for e in s.events],
                'narrative_score': round(s.narrative_score, 4),
                'continuity_issues': s.continuity_issues,
            })

    print(f'Completeness breakdown: {dict(story_completeness)}')
    print(f'Complete stories count: {len(complete_stories)}')
    for cs in complete_stories:
        print(f'  Segment {cs["segment_id"]}: tracks={cs["track_ids"]} events={cs["event_types"]} score={cs["narrative_score"]}')

    # Update the existing results json with the accurate pipeline results
    if OUT_JSON.exists():
        data = json.loads(OUT_JSON.read_text())
    else:
        data = {}

    data['pipeline_results_best_candidate'] = {
        'total_confirmed_person_tracks': len([
            t for t in ctx.metadata.get('all_tracks', [])
            if (t.is_confirmed or t.confirmed_at_frame is not None) and (t.class_name or '').lower() in {'person', 'man', 'woman', 'child', 'baby', 'crowd'}
        ]),
        'min_activity_observations': 5,
        's07_events_count': len(ctx.metadata.get('events', [])),
        'fused_events_count': len(ctx.metadata.get('fused_events', [])),
        'story_segments_count': len(segments),
        'story_completeness': dict(story_completeness),
        'complete_stories_count': len(complete_stories),
        'complete_stories': complete_stories,
    }

    OUT_JSON.write_text(json.dumps(data, indent=2))
    print(f'Updated {OUT_JSON}')
    shutil.rmtree(str(tmpdir), ignore_errors=True)

if __name__ == '__main__':
    asyncio.run(run())
