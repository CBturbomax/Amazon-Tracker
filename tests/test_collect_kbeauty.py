import random

import scraper.collect_kbeauty as ck
from scraper.fetchers.base import FetchResult, now_kst
from tests.fake_amazon import CAPTCHA_PAGE, bestseller_page


class FakeFetcher:
    def __init__(self, pages):
        self.pages = list(pages)

    def fetch(self, url):
        status, html = self.pages.pop(0)
        return FetchResult(url, "fake", now_kst().isoformat(), status=status, html=html)

    def close(self):
        pass


def run(monkeypatch, pages):
    monkeypatch.setattr(ck, "make_fetcher", lambda method, **kw: FakeFetcher(pages))
    return ck.collect_country("US", "fake", (0, 0), random.Random(0), None)


def test_ok_when_both_pages_complete(monkeypatch):
    doc = run(monkeypatch, [(200, bestseller_page(50)), (200, bestseller_page(50))])
    assert doc["status"] == "ok"
    assert len(doc["pages"]) == 2 and all(p["complete"] for p in doc["pages"])
    assert doc["items"][0]["page"] == 1 and doc["pages"][0]["url"].startswith("https://www.amazon.com/")
    assert "html" not in doc["pages"][0]


def test_partial_when_lazy_items_missing(monkeypatch):
    doc = run(monkeypatch, [(200, bestseller_page(30)), (200, bestseller_page(50))])
    assert doc["status"] == "partial"


def test_stops_on_captcha(monkeypatch):
    doc = run(monkeypatch, [(200, CAPTCHA_PAGE), (200, bestseller_page(50))])
    assert doc["status"] == "failed" and len(doc["pages"]) == 1
    assert doc["pages"][0]["outcome"] == "captcha"
