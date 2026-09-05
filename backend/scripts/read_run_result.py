import json
from pathlib import Path

r = json.loads(Path('results/TCE-v1.0/phase6-pipeline-run-archive_001_60s.json').read_text())
f = r['funnel']['funnel']
print('=== FUNNEL ===')
for k,v in f.items():
    print('  %s: %s' % (k, v))
print()
print('=== STAGE SNAPSHOTS ===')
for stage, data in r['stage_log'].items():
    if stage == '_total_pipeline_ms':
        continue
    if not isinstance(data, dict):
        continue
    snap = data.get('metadata_snapshot', {})
    warns = data.get('warnings', [])
    print('  %s: ok=%s, ms=%s' % (stage, data.get('success'), data.get('elapsed_ms')))
    for k,v in snap.items():
        if v not in (None, 'N/A', 'NOT AVAILABLE', {}, 'NOT_AVAILABLE'):
            print('      %s: %s' % (k, v))
    for w in warns[:3]:
        print('      WARN: %s' % str(w)[:120])
