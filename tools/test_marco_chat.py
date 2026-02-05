"""
Run a UX smoke test for the Marco RAG chat (`/api/chat/rag`) against random seeded cities.
Collects: status, latency, answer length, and simple content checks (no placeholders, no source mentions, not empty).

Usage: python3 tools/test_marco_chat.py --count 20
"""

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import aiohttp

SEED = Path(__file__).resolve().parents[1] / 'city_guides' / 'data' / 'seeded_cities.json'
API_URL = 'http://localhost:5010/api/chat/rag'

DEFAULT_QUERIES = [
    "Give me a 3-sentence travel recommendation focused on food and neighborhoods.",
    "What are the top 5 must-see attractions and a recommended half-day itinerary?",
    "What should a first-time visitor know about local transport and safety?",
]


def pick_cities(count):
    data = json.loads(SEED.read_text())
    cities = data.get('cities', {})
    if not cities:
        raise RuntimeError('No seeded cities available')
    # Convert dict to list of city objects
    city_list = [{'name': name, 'countryCode': 'XX'} for name in cities.keys()]
    return random.sample(city_list, min(count, len(city_list)))


async def test_city(session, city, query):
    payload = {
        'query': query,
        'engine': 'google',
        'max_results': 5,
        'city': city.get('name')
    }
    start = time.time()
    try:
        async with session.post(API_URL, json=payload, timeout=30) as resp:
            latency = (time.time() - start)
            status = resp.status
            data = await resp.json()
            answer = data.get('answer') if isinstance(data, dict) else None
            passed = True
            issues = []
            if status != 200:
                passed = False
                issues.append(f'HTTP {status}')
            if not answer or not isinstance(answer, str) or len(answer.strip()) < 30:
                passed = False
                issues.append('empty_or_short_answer')
            low = answer.lower() if answer else ''
            if 'i don' in low or 'as an ai' in low or 'i am' in low:
                # blunt check for model self-reference
                issues.append('model_self_reference')
            if 'http' in low or 'https' in low or 'wikipedia' in low:
                # discourage direct link disclosure in answers
                issues.append('contains_links_or_sources')

            fallback_msg = 'No live web snippets available' in (answer or '')
            if fallback_msg:
                issues.append('fallback_no_live_web')

            return {
                'city': city.get('name'),
                'country': city.get('countryCode'),
                'status': status,
                'latency': latency,
                'answer_len': len(answer) if answer else 0,
                'passed': passed,
                'issues': issues,
                'sample': (answer or '')[:300]
            }
    except Exception as e:
        return {
            'city': city.get('name'),
            'country': city.get('countryCode'),
            'status': 0,
            'latency': time.time() - start,
            'answer_len': 0,
            'passed': False,
            'issues': [f'exception:{e}'],
            'sample': ''
        }


async def main(count, queries):
    cities = pick_cities(count)
    results = []
    async with aiohttp.ClientSession() as session:
        for c in cities:
            q = random.choice(queries)
            r = await test_city(session, c, q)
            print(f"{c.get('name'):30} | {r['status']:3} | {r['latency']:.2f}s | len={r['answer_len']:4} | issues={r['issues']}")
            results.append(r)
    # summary
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    avg_latency = sum(r['latency'] for r in results) / total
    print('\nSUMMARY')
    print('-------')
    print(f'Tested {total} cities. Passed: {passed}/{total}. Avg latency: {avg_latency:.2f}s')
    failures = [r for r in results if not r['passed']]
    if failures:
        print('\nFailures:')
        for f in failures:
            print(f" - {f['city']} ({f['issues']}) sample: {f['sample'][:200]!r}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--queries', type=str, nargs='*', default=DEFAULT_QUERIES)
    args = parser.parse_args()
    asyncio.run(main(args.count, args.queries))
