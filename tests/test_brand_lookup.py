from scraper.brand_lookup import parse_brand


def test_po_brand_row():
    html = """<table><tr class="a-spacing-small po-brand"><td class="a-span3"><span>Brand</span></td>
    <td class="a-span9"><span class="a-size-base po-break-word">La Roche-Posay</span></td></tr></table>
    <a id="bylineInfo">Visit the LRP Store</a>"""
    assert parse_brand(html) == ("La Roche-Posay", "po-brand")


def test_byline_variants():
    assert parse_brand('<a id="bylineInfo">Visit the medicube Store</a>') == ("medicube", "byline")
    assert parse_brand('<a id="bylineInfo">Besuche den CeraVe-Store</a>') == ("CeraVe", "byline")
    assert parse_brand('<a id="bylineInfo">Visiter la boutique Garnier</a>') == ("Garnier", "byline")
    assert parse_brand('<a id="bylineInfo">Visita la tienda de ISDIN</a>') == ("ISDIN", "byline")
    assert parse_brand('<a id="bylineInfo">Visita lo Store di Rilastil</a>') == ("Rilastil", "byline")
    assert parse_brand('<a id="bylineInfo">Brand: Amazon Basics</a>') == ("Amazon Basics", "byline")


def test_missing():
    assert parse_brand("<html></html>") == (None, None)


def test_switches_to_playwright_on_captcha(tmp_path, monkeypatch):
    import json

    import scraper.brand_lookup as bl
    from scraper.fetchers.base import FetchResult, now_kst
    from tests.fake_amazon import CAPTCHA_PAGE

    snap = {"country": "US", "items": [{"asin": "A1", "rank": 1}, {"asin": "A2", "rank": 2}]}
    (tmp_path / "kbeauty" / "US").mkdir(parents=True)
    (tmp_path / "kbeauty" / "US" / "2026-09-28.json").write_text(json.dumps(snap))
    made = []

    class F:
        def __init__(self, method):
            self.method = method

        def fetch(self, url):
            html = CAPTCHA_PAGE if self.method == "curl_cffi" else '<a id="bylineInfo">Visit the COSRX Store</a>'
            return FetchResult(url, self.method, now_kst().isoformat(), status=200, html=html)

        def close(self):
            pass

    def fake_make(method, **kw):
        made.append((method, kw.get("scroll")))
        return F(method)

    monkeypatch.setattr(bl, "make_fetcher", fake_make)
    monkeypatch.setattr(bl.time, "sleep", lambda s: None)
    bl.main(["--data-dir", str(tmp_path), "--max", "5"])
    cache = json.loads((tmp_path / "asin_brands.json").read_text())
    assert cache["A1"]["brand"] == "COSRX" and cache["A2"]["brand"] == "COSRX"
    assert cache["A1"]["method"] == "playwright" and cache["A1"]["tries"] == 1
    assert made[0] == ("curl_cffi", None) and made[1] == ("playwright", False)
