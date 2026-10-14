import json
from datetime import datetime

import scraper.collect_kbeauty as ck
from scraper.fetchers.base import KST
from scraper.markets import bestseller_url
from scraper.snapshot import write_snapshot


def test_german_first_request_uses_explicit_page_one():
    assert bestseller_url('DE', 'beauty', 1) == (
        'https://www.amazon.de/gp/bestsellers/beauty/ref=zg_bs_pg_1_beauty?ie=UTF8&pg=1')


def test_other_markets_keep_working_first_page_route():
    assert bestseller_url('FR', 'beauty', 1) == 'https://www.amazon.fr/gp/bestsellers/beauty'


def test_same_day_recovery_skips_complete_countries(monkeypatch, tmp_path):
    monkeypatch.setattr(ck, 'now_kst', lambda: datetime(2026, 10, 14, 10, 0, tzinfo=KST))
    old_ok = {'status': 'ok', 'date': '2026-10-14', 'items': [{'asin': 'ORIGINAL'}]}
    old_failed = {'status': 'failed', 'date': '2026-10-14', 'items': [],
                  'collected_at': '2026-10-14T09:00:00+09:00'}
    for cc, doc in [('US', old_ok), ('DE', old_failed)]:
        write_snapshot(tmp_path / 'kbeauty' / cc / '2026-10-14.json', doc)
    calls = []
    def collect(cc, *args, **kwargs):
        calls.append(cc)
        return {'status': 'ok', 'date': '2026-10-14', 'items': [{'asin': 'RECOVERED'}],
                'collected_at': '2026-10-14T10:00:00+09:00'}
    monkeypatch.setattr(ck, 'collect_country', collect)
    assert ck.main(['--countries', 'US,DE', '--data-dir', str(tmp_path), '--delay-min', '0', '--delay-max', '0']) == 0
    assert calls == ['DE']
    assert json.loads((tmp_path / 'kbeauty/US/2026-10-14.json').read_text()) == old_ok
    assert json.loads((tmp_path / 'kbeauty/DE/2026-10-14.attempt-090000.json').read_text()) == old_failed
    assert json.loads((tmp_path / 'kbeauty/DE/2026-10-14.json').read_text())['status'] == 'ok'


def test_old_failure_is_never_filled_with_today_products(monkeypatch, tmp_path):
    monkeypatch.setattr(ck, 'now_kst', lambda: datetime(2026, 10, 14, 10, 0, tzinfo=KST))
    path = tmp_path / 'kbeauty/DE/2026-10-13.json'
    original = {'status': 'partial', 'date': '2026-10-13', 'items': [{'asin': 'HISTORICAL'}]}
    write_snapshot(path, original)
    monkeypatch.setattr(ck, 'collect_country', lambda *a, **kw: {'status': 'ok', 'date': '2026-10-14', 'items': []})
    assert ck.main(['--countries', 'DE', '--data-dir', str(tmp_path)]) == 0
    assert json.loads(path.read_text()) == original


def test_all_complete_countries_are_a_successful_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(ck, 'now_kst', lambda: datetime(2026, 10, 14, 10, 0, tzinfo=KST))
    write_snapshot(tmp_path / 'kbeauty/DE/2026-10-14.json', {'status': 'ok', 'items': []})
    def unexpected(*args, **kw):
        raise AssertionError('complete country must not make new requests')
    monkeypatch.setattr(ck, 'collect_country', unexpected)
    assert ck.main(['--countries', 'DE', '--data-dir', str(tmp_path)]) == 0


def test_repeated_attempt_timestamp_does_not_overwrite_archive(tmp_path):
    path = tmp_path / '2026-10-14.json'
    first = {'status': 'failed', 'items': [], 'collected_at': '2026-10-14T09:00:00+09:00', 'n': 1}
    second = {**first, 'n': 2}
    third = {**first, 'status': 'ok', 'n': 3}
    write_snapshot(path, first)
    write_snapshot(path, second)
    write_snapshot(path, third)
    archives = list(tmp_path.glob('*.attempt-*.json'))
    assert len(archives) == 2
    assert {json.loads(p.read_text())['n'] for p in archives} == {1, 2}
