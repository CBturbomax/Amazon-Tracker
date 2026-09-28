"""제품 상세 페이지에서 공식 브랜드명을 읽어 data/asin_brands.json에 쌓는다.

베스트셀러 목록에는 브랜드 칸이 없고, 제품명 앞부분도 브랜드가 아닐 때가 있다
(예: "Effaclar Duo+M" = La Roche-Posay). 그래서 ASIN마다 상세 페이지를 한 번만 열어
브랜드 표기(Brand 행 / "Visit the X Store")를 원문 그대로 저장한다. 한 번 확인한 ASIN은 다시 요청하지 않는다.

    python -m scraper.brand_lookup --max 250
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.fetchers import METHODS, make_fetcher
from scraper.fetchers.base import now_kst
from scraper.markets import MARKETS
from scraper.snapshot import DATA_DIR

CACHE_NAME = "asin_brands.json"

# "Visit the X Store" 류 문구 (나라별)
BYLINE_PATTERNS = [
    re.compile(r"^Visit the (.+?) Store$", re.I),
    re.compile(r"^Besuche den (.+?)-Store$", re.I),
    re.compile(r"^Besuchen Sie den (.+?)-Store$", re.I),
    re.compile(r"^Visiter la boutique (.+)$", re.I),
    re.compile(r"^Visita la tienda de (.+)$", re.I),
    re.compile(r"^Visita lo Store di (.+)$", re.I),
    re.compile(r"^(?:Brand|Marke|Marque|Marca)\s*:\s*(.+)$", re.I),
]


def parse_brand(html: str) -> tuple[str | None, str | None]:
    """(브랜드, 출처) — 출처는 "po-brand" | "byline" | None"""
    soup = BeautifulSoup(html or "", "lxml")
    cell = soup.select_one("tr.po-brand td.a-span9 span") or soup.select_one("tr.po-brand td:nth-of-type(2) span")
    if cell and cell.get_text(strip=True):
        return " ".join(cell.get_text(" ", strip=True).split()), "po-brand"
    by = soup.select_one("#bylineInfo")
    if by:
        text = " ".join(by.get_text(" ", strip=True).split())
        for p in BYLINE_PATTERNS:
            m = p.match(text)
            if m:
                return m.group(1).strip(), "byline"
        if text and len(text) <= 60:
            return text, "byline"
    return None, None


def load_cache(data_dir: Path = DATA_DIR) -> dict[str, dict]:
    p = data_dir / CACHE_NAME
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_cache(cache: dict[str, dict], data_dir: Path = DATA_DIR) -> None:
    p = data_dir / CACHE_NAME
    p.write_text(json.dumps(dict(sorted(cache.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def asins_needing_lookup(data_dir: Path, cache: dict[str, dict]) -> list[tuple[str, str]]:
    """(ASIN, 처음 본 국가) — 최근 스냅샷부터, 캐시에 브랜드가 없는 것만"""
    seen: dict[str, str] = {}
    files = sorted((data_dir / "kbeauty").glob("*/*.json"), reverse=True)
    for f in files:
        if not re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f.name):
            continue
        snap = json.loads(f.read_text(encoding="utf-8"))
        for it in sorted(snap.get("items", []), key=lambda x: x.get("rank") or 999):
            a = it["asin"]
            c = cache.get(a) or {}
            if a in seen or c.get("brand") or c.get("tries", 0) >= 3:
                continue
            seen[a] = snap["country"]
    return list(seen.items())


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="ASIN → 브랜드 (상세 페이지 1회 조회)")
    ap.add_argument("--max", type=int, default=250, help="이번 실행에서 조회할 최대 ASIN 수")
    ap.add_argument("--method", default="curl_cffi", choices=METHODS)
    ap.add_argument("--delay-min", type=float, default=3.0)
    ap.add_argument("--delay-max", type=float, default=8.0)
    ap.add_argument("--stop-after", type=int, default=3, help="연속 차단 횟수에서 중단")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = ap.parse_args(argv)

    cache = load_cache(args.data_dir)
    todo = asins_needing_lookup(args.data_dir, cache)
    print(f"브랜드 미확인 ASIN {len(todo)}개 중 최대 {args.max}개 조회", flush=True)
    todo = todo[: args.max]
    if not todo:
        return 0

    rng = random.Random()
    # 빠른 방식(curl_cffi)이 막히면 브라우저(Playwright)로 바꿔서 이어간다
    methods = [args.method] + (["playwright"] if args.method != "playwright" else [])
    mi = 0
    fetchers: dict[str, object] = {}

    def fetcher(market: str):
        if market not in fetchers:
            kw = {"accept_language": MARKETS[market]["accept_language"]}
            if methods[mi] == "playwright":
                kw["scroll"] = False
            fetchers[market] = make_fetcher(methods[mi], **kw)
        return fetchers[market]

    def lookup(asin: str, cc: str) -> dict:
        entry: dict = {}
        for market in dict.fromkeys(["US", cc]):  # 미국 → (없으면) 처음 본 나라
            fr = fetcher(market).fetch(f"https://{MARKETS[market]['domain']}/dp/{asin}")
            if fr.block:
                return {"error": fr.block, "checked_at": fr.fetched_at}
            brand, source = parse_brand(fr.html) if fr.status == 200 else (None, None)
            if brand:
                return {"brand": brand, "source": source, "domain": MARKETS[market]["domain"],
                        "method": methods[mi], "checked_at": fr.fetched_at}
            entry = {"error": f"status={fr.status}" if fr.status != 200 else "no_brand",
                     "checked_at": fr.fetched_at}
        return entry

    blocks = 0
    i = 0
    try:
        while i < len(todo):
            asin, cc = todo[i]
            if i:
                time.sleep(rng.uniform(args.delay_min, args.delay_max))
            entry = lookup(asin, cc)
            blocked = entry.get("error") in ("captcha", "http_503")
            if blocked and mi + 1 < len(methods):
                for f in fetchers.values():
                    f.close()
                fetchers.clear()
                mi += 1
                print(f"{asin} {entry['error']} → {methods[mi]} 방식으로 전환", flush=True)
                continue  # 같은 ASIN을 새 방식으로 다시
            old = cache.get(asin) or {}
            # 차단은 ASIN 탓이 아니므로 시도 횟수에 넣지 않는다
            new = {**old, **entry, "tries": old.get("tries", 0) + (0 if blocked else 1)}
            if "brand" in entry:
                new.pop("error", None)
            cache[asin] = new
            print(f"{i + 1:>3}/{len(todo)} [{methods[mi]}] {asin} {entry.get('brand') or entry.get('error')}",
                  flush=True)
            blocks = blocks + 1 if blocked else 0
            if blocks >= args.stop_after:
                print(f"연속 차단 {blocks}회 → 중단", flush=True)
                break
            if (i + 1) % 25 == 0:
                save_cache(cache, args.data_dir)  # 중간 저장
            i += 1
    finally:
        for f in fetchers.values():
            f.close()
        save_cache(cache, args.data_dir)
    found = sum(1 for v in cache.values() if v.get("brand"))
    print(f"완료: 캐시 {len(cache)}개 중 브랜드 확인 {found}개 ({now_kst().isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
