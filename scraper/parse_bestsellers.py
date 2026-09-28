"""아마존 베스트셀러 목록 페이지 파서 (/gp/bestsellers/...).

두 가지를 따로 센다.
- 렌더된 카드(`#gridItemRoot`): 순위·ASIN·제품명·가격·평점·평점 수를 뽑는다.
  브라우저 없이 받은 HTML에는 보통 30개만 들어 있다.
- `data-client-recs-list` 속성: 페이지 50개 전체의 ASIN과 순위가 JSON으로 들어 있다.

숫자 변환 전의 원문(price_text, rating_text, rating_count_text)도 같이 남긴다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
DP_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
RATING_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


@dataclass
class ParseResult:
    items: list[dict] = field(default_factory=list)
    recs: list[dict] = field(default_factory=list)  # [{"asin", "rank"}] from data-client-recs-list

    @property
    def rendered_count(self) -> int:
        return len(self.items)

    @property
    def recs_count(self) -> int:
        return len(self.recs)


def parse_bestseller_page(html: str) -> ParseResult:
    soup = BeautifulSoup(html or "", "lxml")
    recs = _parse_recs_list(soup)
    rank_by_asin = {r["asin"]: r["rank"] for r in recs if r.get("rank") is not None}

    roots = soup.select("div#gridItemRoot") or soup.select("div.zg-grid-general-faceout")
    items: list[dict] = []
    seen: set[str] = set()
    for root in roots:
        item = _parse_item(root)
        if not item["asin"] or item["asin"] in seen:
            continue
        seen.add(item["asin"])
        if item["rank"] is None:
            item["rank"] = rank_by_asin.get(item["asin"])
        items.append(item)
    return ParseResult(items=items, recs=recs)


def _parse_recs_list(soup: BeautifulSoup) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for el in soup.select("[data-client-recs-list]"):
        try:
            data = json.loads(el["data-client-recs-list"])
        except (ValueError, TypeError):
            continue
        for entry in data if isinstance(data, list) else []:
            asin = entry.get("id") if isinstance(entry, dict) else None
            if not asin or asin in seen:
                continue
            seen.add(asin)
            rank = (entry.get("metadataMap") or {}).get("render.zg.rank")
            out.append({"asin": asin, "rank": _to_int(rank)})
    return out


def _parse_item(root: Tag) -> dict:
    rank_text = _text(root.select_one(".zg-bdg-text"))
    price_text = _text(
        root.select_one("span[class*='p13n-sc-price']")
        or root.select_one("span.a-price span.a-offscreen")
        or root.select_one(".a-color-price")
    )
    rating_text = _text(root.select_one(".a-icon-alt"))
    rating_count_text = _rating_count_text(root)
    return {
        "rank": _to_int(rank_text),
        "asin": _asin(root),
        "title": _title(root),
        "price_text": price_text,
        "price": parse_price(price_text),
        "rating_text": rating_text,
        "rating": parse_rating(rating_text),
        "rating_count_text": rating_count_text,
        "rating_count": _to_int(rating_count_text),
    }


def _asin(root: Tag) -> str | None:
    for el in [root, *root.select("[data-asin]")]:
        v = el.get("data-asin")
        if v and ASIN_RE.match(v):
            return v
    for el in root.select("div[id]"):
        if ASIN_RE.match(el["id"]):
            return el["id"]
    for a in root.select("a[href*='/dp/']"):
        m = DP_ASIN_RE.search(a["href"])
        if m:
            return m.group(1)
    return None


def _title(root: Tag) -> str | None:
    for sel in ("div[class*='p13n-sc-css-line-clamp']", "div[class*='p13n-sc-truncate']",
                "a.a-link-normal span div"):
        t = _text(root.select_one(sel))
        if t:
            return t
    img = root.select_one("img[alt]")
    return img["alt"].strip() if img and img.get("alt") else None


def _rating_count_text(root: Tag) -> str | None:
    link = root.select_one("a[href*='/product-reviews/']")
    if link:
        t = _text(link.select_one("span.a-size-small")) or _text(link)
        # 링크 텍스트에 평점 문구가 섞인 경우 숫자 덩어리만 남긴다
        if t:
            nums = re.findall(r"\d[\d,.\s]*", t)
            return nums[-1].strip() if nums else None
    return None


def _text(el: Tag | None) -> str | None:
    if el is None:
        return None
    t = " ".join(el.get_text(" ", strip=True).split())
    return t or None


def _to_int(v) -> int | None:
    if v is None:
        return None
    digits = re.sub(r"\D", "", str(v))
    return int(digits) if digits else None


def parse_rating(text: str | None) -> float | None:
    """'4.6 out of 5 stars' / '4,6 von 5 Sternen' → 4.6"""
    if not text:
        return None
    m = RATING_RE.search(text)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v if 0 <= v <= 5 else None


def parse_price(text: str | None) -> float | None:
    """'$12.99' / '12,99 €' / '1.234,56 €' / '$10.99 - $20.99'(첫 값) → float"""
    if not text:
        return None
    m = re.search(r"\d[\d.,\s ]*", text)
    if not m:
        return None
    s = re.sub(r"[\s ]", "", m.group(0)).rstrip(".,")
    if "," in s and "." in s:
        # 뒤에 나오는 기호가 소수점
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) == 2 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None
