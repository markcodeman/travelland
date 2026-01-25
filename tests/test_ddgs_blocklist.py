from city_guides.src.snippet_filters import filter_ddgs_results


def make_res(href, title='t'):
    return {'href': href, 'title': title, 'body': 'snippet'}


def test_filter_ddgs_results_blocks_tripsavvy_and_allows_other():
    results = [
        make_res('https://www.tripsavvy.com/neighborhoods-in-guadalajara-5076271'),
        make_res('https://example.com/guadalajara-neighborhoods'),
        make_res('https://sub.tripadvisor.com/some-page'),
    ]
    blocked_domains = ['tripsavvy.com', 'tripadvisor.com']
    allowed, blocked = filter_ddgs_results(results, blocked_domains)
    assert len(allowed) == 1
    assert allowed[0]['href'].startswith('https://example.com/')
    assert len(blocked) == 2
    assert any('tripsavvy.com' in (r['href']) for r in blocked)


def test_is_blocked_with_subdomains():
    results = [make_res('https://de.tripadvisor.com/foo'), make_res('https://blog.tripsavvy.com/foo')]
    allowed, blocked = filter_ddgs_results(results, ['tripadvisor.com','tripsavvy.com'])
    assert len(allowed) == 0
    assert len(blocked) == 2
