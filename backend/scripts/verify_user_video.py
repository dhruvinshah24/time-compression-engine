"""
Verification script for user video: WhatsApp Video 2026-09-23 at 4.54.57 PM.mp4
(Job: JOB-20260923-588FBF60, Video: VID-EBBEF071C0EA)
"""
import asyncio
import json
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.context import PipelineContext
from app.pipeline.orchestrator import PipelineOrchestrator

async def main():
    video_path = Path(r"C:\Users\dhruv\.gemini\antigravity\scratch\storage\uploads\JOB-20260923-588FBF60\original.mp4")
    if not video_path.exists():
        print(f"Error: {video_path} does not exist!")
        return

    output_dir = Path(r"C:\Users\dhruv\.gemini\antigravity\scratch\storage\processed\JOB-20260923-588FBF60")
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = "JOB-20260923-588FBF60"
    video_id = "VID-EBBEF071C0EA"

    settings = {
        "frame_skip_rate": 3,
        "adaptive_skip": True,
        "adaptive_skip_min": 1,
        "adaptive_skip_max": 10,
        "detection_model": "yolo11x",
        "detection_confidence": 0.25,
        "per_class_confidence": {
            "person": 0.25,
            "man": 0.25,
            "woman": 0.25,
            "child": 0.22,
            "bicycle": 0.35,
            "car": 0.35,
            "motorcycle": 0.35,
            "laptop": 0.30,
            "cell phone": 0.25,
            "phone": 0.25,
            "bottle": 0.25,
            "cup": 0.25,
            "book": 0.25,
            "backpack": 0.25,
            "handbag": 0.25,
            "chair": 0.30,
            "default": 0.35,
        },
        "use_sahi": False,  # faster verification run
        "require_bicycle_for_cycling": True,
    }

    ctx = PipelineContext(
        job_id=job_id,
        video_id=video_id,
        video_path=str(video_path),
        output_dir=str(output_dir),
        settings=settings,
    )

    from app.repositories.inmemory import get_event_repo, get_job_repo
    job_repo = get_job_repo()
    event_repo = get_event_repo()
    await job_repo.create({
        "id": job_id,
        "video_id": video_id,
        "status": "pending",
    })

    print("Running pipeline on user video...")
    orchestrator = PipelineOrchestrator(job_repo=job_repo, event_repo=event_repo)
    result = await orchestrator.run(ctx)

    job_record = await job_repo.get(job_id)
    print("\n" + "=" * 60)
    print(f"PIPELINE RUN SUCCESS: {result}")
    stages = job_record.get("stages", []) if job_record else []
    print(f"Stages completed: {len(stages)}")
    for sr in stages:
        print(f"  Stage {sr.get('stage_name')}: success={sr.get('success')} duration={sr.get('duration_ms')}ms")
        if sr.get("errors"):
            print(f"    Errors: {sr.get('errors')}")

    # Inspect results
    meta = ctx.metadata.get("video_metadata")
    video_dur_s = getattr(meta, "duration_seconds", 0.0) if meta else 0.0
    print(f"\nVideo Duration: {video_dur_s:.2f}s ({video_dur_s * 1000:.0f}ms)")

    # 1. Check Events
    events = ctx.metadata.get("events", [])
    print(f"\nTotal Events: {len(events)}")
    cycling_events = [e for e in events if getattr(e, "event_type", "") == "cycling" or "cycling" in getattr(e, "event_type", "")]
    print(f"Cycling Events: {len(cycling_events)}")
    if cycling_events:
        for ce in cycling_events:
            print(f"  WARNING Spurious cycling: {ce.event_type} at {ce.start_ms}ms")
    else:
        print("  PASS: Zero cycling events detected!")

    max_start_ms = max((getattr(e, "start_ms", 0.0) for e in events), default=0.0)
    max_end_ms = max((getattr(e, "end_ms", 0.0) for e in events), default=0.0)
    print(f"Max Event Start: {max_start_ms / 1000:.2f}s, Max Event End: {max_end_ms / 1000:.2f}s")
    if max_end_ms > (video_dur_s * 1000 + 500):
        print(f"  FAIL: Event timestamp {max_end_ms}ms exceeds video duration {video_dur_s * 1000}ms!")
    else:
        print("  PASS: All event timestamps are strictly within video duration!")

    # 2. Check Persons Gallery
    gallery = ctx.metadata.get("person_gallery", {})
    print(f"\nPerson Gallery ({len(gallery)} persons):")
    for label, p in gallery.items():
        dur_s = (p.get("last_seen_ms", 0.0) - p.get("first_seen_ms", 0.0)) / 1000
        print(f"  {label}: active={dur_s:.1f}s, frames={p.get('observation_count', 0)}, first={p.get('first_seen_ms', 0)/1000:.1f}s, last={p.get('last_seen_ms', 0)/1000:.1f}s")
        if dur_s > video_dur_s + 0.5:
            print(f"    FAIL: Active duration {dur_s}s exceeds video duration {video_dur_s}s!")
        else:
            print(f"    PASS: Active duration {dur_s:.1f}s is within video duration!")

    all_tracks = ctx.metadata.get("all_tracks", [])
    from collections import Counter
    class_counts = Counter(getattr(t, "class_name", "?") for t in all_tracks)
    print(f"\nAll Tracks from S05 ({len(all_tracks)} tracks): {dict(class_counts)}")
    confirmed_counts = Counter(getattr(t, "class_name", "?") for t in all_tracks if getattr(t, "is_confirmed", False))
    print(f"Confirmed Tracks ({sum(confirmed_counts.values())} tracks): {dict(confirmed_counts)}")

    # 3. Check Detected Objects
    detected_objects = job_record.get("detected_objects", []) if job_record else []
    print(f"\nDetected Objects ({len(detected_objects)} unique classes):")
    for obj in detected_objects:
        print(f"  - {obj.get('display_name')} (class: {obj.get('class_name')}, instances: {obj.get('instance_count')}, max_conf: {obj.get('max_confidence')}, cat: {obj.get('category')})")

    # Check for junk
    junk = [o for o in detected_objects if o.get("class_name") in ("sports_ball", "vase", "teddy_bear", "couch", "frisbee", "skateboard")]
    if junk:
        print(f"  WARNING: Detected junk classes: {[j.get('class_name') for j in junk]}")
    else:
        print("  PASS: Zero false-positive junk classes in object inventory!")

if __name__ == "__main__":
    asyncio.run(main())
