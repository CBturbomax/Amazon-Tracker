from scraper.classify import classify, detect_block
from scraper.parse_bestsellers import parse_bestseller_page, parse_price, parse_rating
from tests.fake_amazon import CAPTCHA_PAGE, DOG_503_PAGE, asin, bestseller_page


def test_rendered_cards_and_recs_list():
    r = parse_bestseller_page(bestseller_page(n_rendered=30, n_total=50))
    assert r.rendered_count == 30
    assert r.recs_count == 50
    assert [x["rank"] for x in r.recs[:3]] == [1, 2, 3]
    first = r.items[0]
    assert first == {
        "rank": 1,
        "asin": asin(1),
        "title": "medicube Test Product 1 Serum 50ml",
        "price_text": "$1.99",
        "price": 1.99,
        "rating_text": "4.1 out of 5 stars",
        "rating": 4.1,
        "rating_count_text": "1,000",
        "rating_count": 1000,
    }
    assert r.items[29]["rank"] == 30


def test_full_page():
    r = parse_bestseller_page(bestseller_page(n_rendered=50))
    assert r.rendered_count == 50
    assert len({x["asin"] for x in r.items}) == 50


def test_empty_or_garbage_html():
    assert parse_bestseller_page("").rendered_count == 0
    assert parse_bestseller_page("<html><body>hi</body></html>").recs_count == 0


def test_price_formats():
    assert parse_price("$12.99") == 12.99
    assert parse_price("$1,234.50") == 1234.5
    assert parse_price("12,99 €") == 12.99
    assert parse_price("1.234,56 €") == 1234.56
    assert parse_price("£8.49") == 8.49
    assert parse_price("$10.99 - $20.99") == 10.99
    assert parse_price(None) is None
    assert parse_price("Currently unavailable") is None


def test_rating_formats():
    assert parse_rating("4.6 out of 5 stars") == 4.6
    assert parse_rating("4,6 von 5 Sternen") == 4.6
    assert parse_rating("4,5 sur 5 étoiles") == 4.5
    assert parse_rating(None) is None


def test_block_detection():
    assert detect_block(200, CAPTCHA_PAGE) == "captcha"
    assert detect_block(503, DOG_503_PAGE) == "http_503"
    assert detect_block(200, DOG_503_PAGE) == "http_503"
    assert detect_block(503, "") == "http_503"
    assert detect_block(200, bestseller_page()) is None


def test_classify():
    assert classify(200, None, None, 30) == "ok"
    assert classify(200, None, None, 0) == "parse_fail"
    assert classify(200, "captcha", None, 0) == "captcha"
    assert classify(404, None, None, 0) == "http_other"
    assert classify(None, None, "ConnectionError", 0) == "error"
