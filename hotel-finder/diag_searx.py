import json
from search_provider import searx_raw_queries, searx_search_hotels, _get_instances_from_env

insts = _get_instances_from_env()[:8]
print('Instances used:', json.dumps(insts, indent=2))
raw = searx_raw_queries('NYC','2025-12-20','2025-12-21',1)
for r in raw:
    print('\nInstance:', r.get('instance'))
    print('Status:', r.get('status_code'))
    if r.get('json') is None:
        print('No JSON (error or non-JSON response). Error:', r.get('error'))
    else:
        rs = r['json'].get('results') if isinstance(r['json'], dict) else None
        print('results count:', len(rs) if rs is not None else 'N/A')
        if rs:
            for i, s in enumerate(rs[:3]):
                print('  sample title:', s.get('title'))
                print('  sample content:', (s.get('content') or s.get('snippet') or '')[:200])

print('\n--- Parsed Offers ---')
res = searx_search_hotels('NYC','2025-12-20','2025-12-21',1, max_results=20)
print('Parsed count:', res.get('count'))
if res.get('hotels'):
    print(json.dumps(res['hotels'][:5], indent=2))
else:
    print('No offers parsed.')
