import semantic

SITES = [
    'https://en.wikipedia.org/wiki/New_York_City',
    'https://en.wikipedia.org/wiki/Paris',
]

def run_demo():
    print('Ingesting...')
    n = semantic.ingest_urls(SITES)
    print('Indexed chunks:', n)
    print('Searching for "best museums"')
    res = semantic.semantic_search('best museums', top_k=5)
    for r in res:
        print(r['score'], r['meta']['source'], r['meta']['snippet'][:200])

if __name__ == '__main__':
    run_demo()
