import random

import pytest

import scraper.collect_kbeauty as ck
from scraper.classify import detect_block
from scraper.fetchers.base import FetchResult, now_kst
from tests.fake_amazon import CAPTCHA_PAGE, DOG_503_PAGE, bestseller_page


@pytest.mark.parametrize('message', [
    'Klicke auf die Schaltfläche unten, um mit dem Einkauf fortzufahren',
    'Cliquez sur le bouton ci-dessous pour continuer vos achats',
])
def test_localized_continue_shopping_is_captcha(message):
    html = f'<html><h4>{message}</h4><form action="/errors_page/validateCaptcha"></form></html>'
    assert detect_block(200, html) == 'captcha'


class SequenceFetcher:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []
        self.closed = False

    def fetch(self, url):
        self.urls.append(url)
        status, html, error = next(self.responses)
        return FetchResult(url, 'fake', now_kst().isoformat(), status=status,
                           final_url=url, html=html, error=error)

    def close(self):
        self.closed = True


def collect(monkeypatch, responses, tmp_path=None, country='DE'):
    fetcher = SequenceFetcher(responses)
    monkeypatch.setattr(ck, 'make_fetcher', lambda *a, **kw: fetcher)
    doc = ck.collect_country(country, 'fake', (0, 0), random.Random(0), tmp_path)
    assert fetcher.closed
    return doc, fetcher


def good(page=1):
    return (200, bestseller_page(50, start_rank=1 if page == 1 else 51), None)


def test_small_200_retries_and_preserves_attempt_metadata(monkeypatch, tmp_path):
    doc, f = collect(monkeypatch, [(200, '<html>temporarily empty</html>', None), good(), good(2)], tmp_path)
    assert doc['status'] == 'ok'
    assert len(doc['items']) == 100
    assert len({i['asin'] for i in doc['items']}) == 100
    attempts = doc['pages'][0]['attempts']
    assert len(attempts) == 2
    assert attempts[0]['response_issue'] == 'unexpected_small_html'
    assert attempts[0]['rendered_count'] == 0
    assert attempts[1]['complete']
    assert len(f.urls) == 3
    assert len(list(tmp_path.glob('*.html'))) == 1


def test_exhaustion_uses_explicit_first_page_route(monkeypatch):
    empty = (200, '<html>empty</html>', None)
    doc, f = collect(monkeypatch, [empty, empty, good(), good(2)])
    assert doc['status'] == 'ok'
    assert 'pg=1' in f.urls[2]
    assert '/ref=zg_bs_pg_1_beauty' in f.urls[2]


def test_retry_budget_keeps_country_partial(monkeypatch):
    empty = (200, '<html>empty</html>', None)
    doc, f = collect(monkeypatch, [empty, empty, empty, good(2)])
    assert doc['status'] == 'partial'
    assert len(doc['items']) == 50
    assert len(f.urls) == 4
    assert not doc['pages'][0]['complete']


def test_failed_retries_keep_best_partial_without_combining_pages(monkeypatch):
    doc, _ = collect(monkeypatch, [(200, bestseller_page(30), None),
                                 (200, '<html>empty</html>', None),
                                 (200, bestseller_page(20), None), good(2)])
    assert doc['status'] == 'partial'
    assert len(doc['items']) == 80
    assert doc['pages'][0]['rendered_count'] == 30
    assert len(doc['pages'][0]['attempts']) == 3


@pytest.mark.parametrize('response', [(200, CAPTCHA_PAGE, None), (503, DOG_503_PAGE, None),
    (200, '<form action="/errors_page/validateCaptcha"></form>', None),
    (429, '<html>rate limited</html>', None), (403, '<html>denied</html>', None)])
def test_block_never_retries_or_requests_next_page(monkeypatch, response):
    doc, f = collect(monkeypatch, [response])
    assert doc['status'] == 'failed'
    assert len(f.urls) == 1


def test_block_after_partial_still_stops_without_promoting_country(monkeypatch):
    doc, f = collect(monkeypatch, [(200, bestseller_page(30), None), (200, CAPTCHA_PAGE, None)])
    assert doc['status'] == 'partial'
    assert len(doc['items']) == 30
    assert not doc['pages'][0]['complete']
    assert doc['pages'][0]['attempts'][-1]['outcome'] == 'captcha'
    assert len(f.urls) == 2


def test_network_error_can_recover(monkeypatch):
    doc, _ = collect(monkeypatch, [(None, '', 'TimeoutError: timed out'), good(), good(2)])
    assert doc['status'] == 'ok'


def test_second_page_partial_can_recover_without_mixing_attempts(monkeypatch):
    doc, _ = collect(monkeypatch, [good(), (200, bestseller_page(30, start_rank=51), None), good(2)])
    assert doc['status'] == 'ok'
    assert len(doc['items']) == 100
    assert len(doc['pages'][1]['attempts']) == 2
    assert len({i['asin'] for i in doc['items']}) == 100


@pytest.mark.parametrize('status', [400, 404])
def test_permanent_http_error_is_not_retried(monkeypatch, status):
    doc, fetcher = collect(monkeypatch, [(status, '<html>not found</html>', None), good(2)])
    assert doc['status'] == 'partial'
    assert len(fetcher.urls) == 2
    assert len(doc['pages'][0]['attempts']) == 1


def test_duplicate_first_page_cannot_be_complete_top100(monkeypatch):
    doc, _ = collect(monkeypatch, [good(), good(), good(), good()])
    assert doc['status'] == 'partial'
    assert not doc['pages'][1]['complete']


def test_short_recommendation_list_cannot_be_complete_top100(monkeypatch):
    short = (200, bestseller_page(10, n_total=10), None)
    doc, _ = collect(monkeypatch, [short, short, short, good(2)])
    assert doc['status'] == 'partial'
    assert not doc['pages'][0]['complete']


def test_attempt_budget_must_be_positive(monkeypatch):
    with pytest.raises(ValueError, match='max_attempts'):
        ck.collect_country('DE', 'fake', (0, 0), random.Random(0), None, max_attempts=0)


def test_retry_delay_backs_off_without_retrying_blocks(monkeypatch):
    sleeps = []
    monkeypatch.setattr(ck.time, 'sleep', sleeps.append)
    empty = (200, '<html>empty</html>', None)
    fetcher = SequenceFetcher([empty, empty, good(), good(2)])
    monkeypatch.setattr(ck, 'make_fetcher', lambda *a, **kw: fetcher)
    doc = ck.collect_country('FR', 'fake', (3, 3), random.Random(0), None)
    assert doc['status'] == 'ok'
    assert sleeps == [3, 6, 3]


def test_recommendation_and_rendered_asins_must_match(monkeypatch):
    from tests.fake_amazon import asin
    wrong = bestseller_page(50).replace(f'&quot;id&quot;: &quot;{asin(1)}&quot;',
                                       '&quot;id&quot;: &quot;B0OTHER001&quot;')
    doc, _ = collect(monkeypatch, [(200, wrong, None)] * 3 + [good(2)])
    assert doc['status'] == 'partial'
    assert not doc['pages'][0]['complete']


def test_recommendation_ranks_must_match_each_rendered_asin(monkeypatch):
    wrong = bestseller_page(50).replace('&quot;render.zg.rank&quot;: &quot;1&quot;',
                                       '&quot;render.zg.rank&quot;: &quot;swap&quot;')
    wrong = wrong.replace('&quot;render.zg.rank&quot;: &quot;2&quot;',
                          '&quot;render.zg.rank&quot;: &quot;1&quot;')
    wrong = wrong.replace('&quot;render.zg.rank&quot;: &quot;swap&quot;',
                          '&quot;render.zg.rank&quot;: &quot;2&quot;')
    doc, _ = collect(monkeypatch, [(200, wrong, None)] * 3 + [good(2)])
    assert doc['status'] == 'partial'
    assert not doc['pages'][0]['complete']


@pytest.mark.parametrize('country', ['DE', 'FR'])
def test_unrecovered_country_stays_null_in_both_builds(monkeypatch, country):
    from build.brands import build_brands, BrandResolver, COUNTRY_ORDER
    from build.build_site import build_kbeauty
    from scraper.brands import load_companies
    empty = (200, '<html>empty</html>', None)
    partial, _ = collect(monkeypatch, [empty, empty, empty, good(2)], country=country)
    records = {day: {cc: {'status': 'ok', 'collected_at': day + 'T09:00:00+09:00',
                          'items': [{'asin': 'A', 'title': 'medicube pad', 'rank': 1}]}
                     for cc in COUNTRY_ORDER} for day in ['2026-10-12', '2026-10-13', '2026-10-14']}
    records['2026-10-13'][country] = partial
    resolver = BrandResolver({'aliases': {'Medicube': ['medicube']}, 'kbeauty': []}, {})
    brands = build_brands(records, [], resolver)
    assert brands['series']['Medicube']['values']['total'] == [6, None, 6]
    assert brands['series']['Medicube']['values'][country] == [1, None, 1]
    assert brands['series']['Medicube']['values']['US'] == [1, 1, 1]
    site = build_kbeauty(records, load_companies(), {})
    assert site['days']['2026-10-13']['grand_total'] is None
    assert site['days']['2026-10-14']['grand_total_delta'] is None
    assert site['days']['2026-10-14']['countries'][country]['delta'] is None
