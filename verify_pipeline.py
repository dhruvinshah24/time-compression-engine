"""
End-to-end pipeline verification script.
Runs: health check -> empty state -> upload -> pipeline poll -> post-checks.
"""
import requests
import json
import time
import sys

BASE = 'http://localhost:8000/api/v1'

print("=" * 60)
print("TCE v1.0.1  End-to-End Verification")
print("=" * 60)

# 1. Health check
try:
    h = requests.get(f'{BASE}/health', timeout=5)
    print(f'\n[HEALTH] {h.status_code} -> {h.json()}')
except Exception as e:
    print(f'[HEALTH] FAILED: {e}')
    sys.exit(1)

# 2. Empty state
analytics = requests.get(f'{BASE}/analytics/stats').json()
print(f'[ANALYTICS] has_data={analytics["has_data"]}  total_videos={analytics["total_videos"]}')

# 3. Upload
print('\n[UPLOAD] Sending test_video.mp4 ...')
with open('test_real.mp4', 'rb') as f:
    resp = requests.post(
        f'{BASE}/upload/',
        files={'file': ('office_test.mp4', f, 'video/mp4')},
        data={'source_domain': 'cctv'},
    )

print(f'  HTTP {resp.status_code}')
if resp.status_code != 200:
    print('  ERROR:', resp.text[:400])
    sys.exit(1)

result   = resp.json()
job_id   = result['job_id']
video_id = result['video_id']
meta     = result.get('metadata', {})

print(f'  job_id      = {job_id}')
print(f'  video_id    = {video_id}')
print(f'  filename    = {result["filename"]}')
print(f'  profile     = {meta.get("profile", "?")}')
print(f'  duration    = {meta.get("duration_hms", "?")}')
print(f'  est_frames  = {meta.get("estimated_frames", "?")}')
print(f'  ffprobe     = {"OK" if meta.get("fps") else "NOT INSTALLED (fallback mode)"}')

# 4. Poll job
print(f'\n[PIPELINE] Polling {job_id} (max 120s) ...')
deadline = time.time() + 120
final_job = None

while time.time() < deadline:
    time.sleep(2)
    job = requests.get(f'{BASE}/jobs/{job_id}').json()
    status   = job.get('status', '?')
    progress = job.get('progress', 0)
    stage    = job.get('current_stage_label') or job.get('current_stage') or '?'
    print(f'  [{int(time.time() % 1000):4d}]  {status:12s}  {progress:3d}%  {stage}')

    if status in ('completed', 'failed', 'cancelled'):
        final_job = job
        break

if not final_job:
    print('  TIMEOUT: pipeline did not finish within 120 seconds')
    sys.exit(1)

# 5. Stage summary
print(f'\n[STAGES]')
for s in final_job.get('stages', []):
    icon = 'OK' if s['status'] == 'success' else ('FAIL' if s['status'] == 'failed' else '    ')
    dur  = f'{s["duration_ms"]}ms' if s.get('duration_ms') is not None else '    ?'
    m    = '  '.join(f'{k}={v}' for k, v in list((s.get('metrics') or {}).items())[:3])
    print(f'  [{icon}]  {s["label"]:30s}  {dur:10s}  {m}')

if final_job.get('status') == 'failed':
    print(f'\n  FAILED AT: {final_job.get("failed_stage")}')
    print(f'  ERROR:     {final_job.get("error")}')

# 6. Post-pipeline state
print(f'\n[POST-PIPELINE]')
videos    = requests.get(f'{BASE}/videos/').json()
events    = requests.get(f'{BASE}/events/').json()
analytics2= requests.get(f'{BASE}/analytics/stats').json()
timeline  = requests.get(f'{BASE}/timeline/{video_id}').json()
summary   = requests.get(f'{BASE}/summary/{video_id}').json()

print(f'  Videos    : {len(videos)}')
print(f'  Events    : {len(events)}')
print(f'  Analytics has_data : {analytics2["has_data"]}')
print(f'  Timeline  events   : {timeline.get("event_count", 0)}')
print(f'  Summary   status   : {summary.get("status")}')

print('\n' + '=' * 60)
if final_job.get('status') == 'completed':
    print('RESULT: PASS - full pipeline ran end-to-end')
else:
    print(f'RESULT: PIPELINE STATUS = {final_job.get("status")}')
print('=' * 60)
