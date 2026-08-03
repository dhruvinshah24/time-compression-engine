"""Live watcher - polls every 3s and shows what the pipeline is doing."""
import requests
import time

BASE = "http://localhost:8000/api/v1"
known = set()

try:
    jobs = requests.get(f"{BASE}/jobs/").json()
    known = {j["id"] for j in jobs}
except Exception:
    pass

print("Watching for new jobs... Upload your video in the browser now.")

while True:
    time.sleep(3)
    try:
        jobs = requests.get(f"{BASE}/jobs/").json()
    except Exception as e:
        print(f"Poll error: {e}")
        continue

    for j in jobs:
        jid = j["id"]
        if jid not in known:
            known.add(jid)
            print(f"\n  New job: {jid}  file={j.get('filename', '?')}")

        status = j.get("status", "?")
        progress = j.get("progress", 0)
        stage = j.get("current_stage_label") or j.get("current_stage") or "?"

        if status not in ("completed", "failed", "cancelled"):
            print(f"  [{jid}]  {status:12s}  {progress:3d}%  {stage}")

        # If just completed, run the full diagnosis
        if status in ("completed", "failed") and f"{jid}_done" not in known:
            known.add(f"{jid}_done")
            print(f"\n{'='*60}")
            print(f"JOB FINISHED: {jid}  status={status}")
            for s in j.get("stages", []):
                m = s.get("metrics") or {}
                icon = "OK" if s["status"] == "success" else "FAIL"
                key_metrics = "  ".join(f"{k}={v}" for k, v in list(m.items())[:4])
                print(f"  [{icon}]  {s['label']:30s}  {key_metrics}")
                if s.get("errors"):
                    print(f"       ERROR: {s['errors'][0]}")

            # Print detections
            ev = requests.get(f"{BASE}/events/").json()
            print(f"\nEvents generated: {len(ev)}")
            for e in ev[:15]:
                ts = e.get("start_time_ms", 0) / 1000
                te = e.get("end_time_ms", 0) / 1000
                print(f"  [{ts:.1f}s-{te:.1f}s]  {e.get('event_type','?'):25s}  conf={e.get('confidence',0):.2f}")
            print("="*60)
