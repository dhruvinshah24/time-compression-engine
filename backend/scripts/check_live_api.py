import urllib.request
import json

url = "http://localhost:8000/api/v1/timeline/VID-EBBEF071C0EA"
with urllib.request.urlopen(url) as resp:
    r = json.loads(resp.read().decode())

print("=== LIVE TIMELINE VERIFICATION ===")
print("Video ID:", r.get("video_id"))
print("Filename:", r.get("filename"))
print("Duration:", r.get("metadata", {}).get("duration_hms"))
print("Event Count:", r.get("event_count"))
print("Unique Persons:", r.get("unique_persons"))

print("\n=== IDENTIFIED PERSONS ===")
for p in r.get("persons", []):
    first_s = p.get("first_seen_ms", 0) / 1000
    last_s = p.get("last_seen_ms", 0) / 1000
    dur = (p.get("last_seen_ms", 0) - p.get("first_seen_ms", 0)) / 1000
    cnt = p.get("observation_count")
    lbl = p.get("person_label")
    crop = p.get("crop_url")
    print(f"  {lbl}: active={dur:.1f}s, frames={cnt}, span=[{first_s:.1f}s - {last_s:.1f}s], crop={crop}")

print("\n=== DETECTED OBJECTS ===")
for o in r.get("detected_objects", []):
    print(f"  - {o.get('display_name')} (class: {o.get('class_name')}, instances: {o.get('instance_count')}, max_conf: {o.get('max_confidence')}, cat: {o.get('category')})")

print("\n=== TIMELINE EVENTS ===")
events = r.get("events", [])
for e in events:
    s = e.get("start_ms", 0) / 1000
    end = e.get("end_ms", 0) / 1000
    t = e.get("event_type")
    c = e.get("confidence")
    print(f"  - {t:25s} [{s:5.1f}s - {end:5.1f}s] conf={c:.2f}")

# Assertions
dur_s = 59.39
assert all(p.get("last_seen_ms", 0) / 1000 <= dur_s + 0.1 for p in r.get("persons", [])), "Person last_seen exceeds duration!"
assert not any("cycling" in e.get("event_type", "").lower() for e in events), "Spurious cycling detected!"
assert not any(o.get("class_name") in ("sports_ball", "vase", "teddy_bear", "couch") for o in r.get("detected_objects", [])), "Junk objects detected!"
print("\nALL GROUND-TRUTH VERIFICATION CHECKS PASSED PERFECTLY!")
