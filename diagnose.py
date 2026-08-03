"""
Diagnose last job from the API and print a full human-readable report.
Usage: python diagnose.py [job_id]   (omit job_id to use the latest job)
"""
import sys
import requests
import json

BASE = "http://localhost:8000/api/v1"

jobs = requests.get(f"{BASE}/jobs/").json()
if not jobs:
    print("No jobs in store. Upload a video first.")
    sys.exit(0)

if len(sys.argv) > 1:
    job_id = sys.argv[1]
    j = next((j for j in jobs if j["id"] == job_id), None)
    if not j:
        print(f"Job {job_id} not found")
        sys.exit(1)
else:
    j = jobs[-1]

print("=" * 70)
print(f"Job:      {j['id']}")
print(f"Video:    {j.get('filename', '?')}")
print(f"Status:   {j['status']}  ({j['progress']}%)")
print(f"Duration: {j.get('video_metadata', {}).get('duration_hms', '?')}")
print(f"Profile:  {j.get('video_metadata', {}).get('profile', '?')}")
print("=" * 70)

print("\nSTAGE BREAKDOWN:")
for s in j.get("stages", []):
    icon = "✓ OK  " if s["status"] == "success" else ("✗ FAIL" if s["status"] == "failed" else "○     ")
    m = s.get("metrics") or {}
    dur = f"{s.get('duration_ms', 0):>6}ms"
    mstr = "  ".join(f"{k}={v}" for k, v in list(m.items())[:4])
    print(f"  {icon}  {s['label']:30s}  {dur}  {mstr}")
    if s.get("errors"):
        for e in s["errors"]:
            print(f"          ERROR: {e}")
    if s.get("warnings"):
        for w in s["warnings"][:2]:
            print(f"          WARN:  {w}")

print("\nKEY NUMBERS:")
for s in j.get("stages", []):
    m = s.get("metrics") or {}
    n = s["name"]
    if n == "s02_extract":
        print(f"  Frames extracted:     {m.get('frames_extracted', '?')}  (skip_rate={m.get('frame_skip_rate', '?')})")
    if n == "s03_scene_detect":
        print(f"  Keyframes selected:   {m.get('keyframes_selected', '?')}  /  {m.get('total_frames_analyzed', '?')}  analyzed")
        print(f"  Duplicate frames:     {m.get('duplicate_frames', '?')}  (rate={m.get('duplicate_rate', '?')})")
    if n == "s04_object_detect":
        print(f"  Frames processed:     {m.get('total_frames_processed', '?')}")
        print(f"  Total detections:     {m.get('total_detections', '?')}")
        print(f"  Frames w/ detections: {m.get('frames_with_detections', '?')}")
        print(f"  Detection rate:       {m.get('detection_rate', '?')}")
        print(f"  Classes:              {m.get('detections_by_class', m.get('classes_detected', '?'))}")
    if n == "s05_track":
        print(f"  Tracks created:       {m.get('total_tracks_created', '?')}")
        print(f"  Confirmed tracks:     {m.get('confirmed_tracks', '?')}")
    if n == "s07_event_understand":
        print(f"  Events generated:     {m.get('total_events', '?')}")
        print(f"  Event types:          {m.get('events_by_type', '?')}")

print("\nEVENTS:")
events = requests.get(f"{BASE}/events/").json()
if not events:
    print("  (none)")
else:
    for e in events[:20]:
        ts = e.get("start_time_ms", 0) / 1000
        te = e.get("end_time_ms", 0) / 1000
        print(f"  [{ts:6.1f}s - {te:6.1f}s]  {e.get('event_type', '?'):25s}  conf={e.get('confidence', 0):.2f}  {e.get('description', '')}")

print("\nFULL PIPELINE LOGS:")
for log in j.get("logs", [])[:60]:
    print(" ", log)
print("=" * 70)
