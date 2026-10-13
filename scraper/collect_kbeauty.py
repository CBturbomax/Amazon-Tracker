"""레이어 1: 국가별 Beauty 베스트셀러 Top 100 수집 → data/kbeauty/{국가}/{날짜}.json

    python -m scraper.collect_kbeauty                    # 5개국, Playwright
    python -m scraper.collect_kbeauty --countries US --method curl_cffi

스냅샷에는 원자료(파싱된 필드 + 원문 텍스트 + 요청 메타)만 저장한다.
회사 매칭·집계는 build 단계에서 한다 (원칙 5).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from scraper.classify import classify
from scraper.fetchers import METHODS, make_fetcher
from scraper.fetchers.base import now_kst
from scraper.markets import MARKETS, bestseller_url
from scraper.parse_bestsellers import ParseResult, parse_bestseller_page
from scraper.snapshot import DATA_DIR, write_snapshot

ROOT = Path(__file__).resolve().parents[1]
SLUG = "beauty"
PAGES = (1, 2)
SCHEMA_VERSION = 1


def collect_country(country: str, method: str, delay: tuple[float, float], rng: random.Random,
                    html_dir: Path | None, max_attempts: int = 3) -> dict:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    market = MARKETS[country]
    started = now_kst()
    pages_meta: list[dict] = []
    items: list[dict] = []
    recs: list[dict] = []
    try:
        fetcher = make_fetcher(method, accept_language=market["accept_language"])
    except Exception as e:
        return _doc(country, method, started, "failed", [], [], [],
                    error=f"init: {type(e).__name__}: {str(e).splitlines()[0]}")
    try:
        for i, pg in enumerate(PAGES):
            if i > 0:
                time.sleep(rng.uniform(*delay))
            selected = None
            attempts = []
            stop = False
            for attempt in range(1, max_attempts + 1):
                if attempt > 1:
                    # Back off without changing session/IP or bypassing a challenge.
                    time.sleep(rng.uniform(*delay) * (2 ** (attempt - 2)))
                url = bestseller_url(country, SLUG, pg)
                if pg == 1 and attempt == max_attempts and attempt > 1:
                    url += "/ref=zg_bs_pg_1_beauty?ie=UTF8&pg=1"
                fr = fetcher.fetch(url)
                parsed = parse_bestseller_page(fr.html) if fr.status == 200 and fr.html and not fr.block and not fr.error else ParseResult()
                outcome = classify(fr.status, fr.block, fr.error, parsed.rendered_count)
                expected = set(range((pg - 1) * 50 + 1, pg * 50 + 1))
                complete = (outcome == "ok" and parsed.rendered_count == 50 and parsed.recs_count == 50
                            and {it.get("rank") for it in parsed.items} == expected
                            and {r.get("rank") for r in parsed.recs} == expected
                            and {it["asin"]: it.get("rank") for it in parsed.items}
                            == {r["asin"]: r.get("rank") for r in parsed.recs}
                            and not ({it["asin"] for it in parsed.items} & {it["asin"] for it in items}))
                issue = None
                if outcome == "parse_fail":
                    issue = "unexpected_small_html" if len(fr.html.encode("utf-8")) < 20000 else "no_products"
                elif outcome == "ok" and not complete:
                    issue = "incomplete_or_wrong_page"
                meta = {**fr.meta(), "page": pg, "attempt": attempt, "outcome": outcome,
                        "complete": complete, "response_issue": issue,
                        "rendered_count": parsed.rendered_count, "recs_count": parsed.recs_count}
                attempts.append(meta)
                # Keep one response per page; never combine products from different attempts.
                if selected is None or complete or parsed.rendered_count > selected[1].rendered_count:
                    selected = (meta, parsed)
                print(f"[{country}] pg={pg} attempt={attempt}/{max_attempts} {outcome} "
                      f"status={fr.status} cards={parsed.rendered_count} recs={parsed.recs_count} "
                      f"complete={complete} bytes={meta['html_bytes']} {fr.elapsed_s}s"
                      + (f" err={fr.error}" if fr.error else ""), flush=True)
                if html_dir and fr.html and not complete:
                    html_dir.mkdir(parents=True, exist_ok=True)
                    (html_dir / f"kbeauty_{country}_p{pg}_a{attempt}_{outcome}.html").write_text(fr.html, encoding="utf-8")
                stop = bool(fr.block) or fr.status in (403, 429, 503)
                retryable = outcome in ("error", "parse_fail") or (outcome == "ok" and not complete)
                if stop or complete or not retryable:
                    break
            page_meta, parsed = selected
            pages_meta.append({**page_meta, "attempts": attempts})
            items.extend({**it, "page": pg} for it in parsed.items)
            recs.extend({**r, "page": pg} for r in parsed.recs)
            if stop:
                break  # 차단이면 더 요청하지 않는다
    finally:
        fetcher.close()

    if pages_meta and len(pages_meta) == len(PAGES) and all(p["complete"] for p in pages_meta):
        status = "ok"
    elif items:
        status = "partial"
    else:
        status = "failed"
    return _doc(country, method, started, status, pages_meta, items, recs)


def _doc(country, method, started, status, pages, items, recs, error=None) -> dict:
    market = MARKETS[country]
    return {
        "schema": SCHEMA_VERSION,
        "layer": "kbeauty",
        "country": country,
        "domain": market["domain"],
        "category": SLUG,
        "date": started.date().isoformat(),
        "collected_at": started.isoformat(timespec="seconds"),
        "method": method,
        "status": status,
        "error": error,
        "pages": pages,
        "items": items,
        "recs": recs,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="K뷰티 모니터링: 국가별 Beauty Top 100 수집")
    ap.add_argument("--countries", default=",".join(MARKETS))
    ap.add_argument("--method", default="playwright", choices=METHODS)
    ap.add_argument("--delay-min", type=float, default=3.0)
    ap.add_argument("--delay-max", type=float, default=8.0)
    ap.add_argument("--max-attempts", type=int, default=3, help="페이지당 최대 요청 횟수 (차단이면 즉시 중단)")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--html-dir", type=Path, default=ROOT / "reports" / "collect_html",
                    help="불완전 수집 페이지의 HTML 저장 위치 (git 제외)")
    args = ap.parse_args(argv)
    if args.max_attempts < 1 or args.delay_min < 0 or args.delay_max < args.delay_min:
        ap.error("max-attempts >= 1 및 0 <= delay-min <= delay-max 필요")
    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    unknown = [c for c in countries if c not in MARKETS]
    if unknown:
        ap.error(f"알 수 없는 국가: {unknown}")

    rng = random.Random()
    summary = []
    for j, cc in enumerate(countries):
        if j > 0:
            time.sleep(rng.uniform(args.delay_min, args.delay_max))
        doc = collect_country(cc, args.method, (args.delay_min, args.delay_max), rng, args.html_dir,
                              max_attempts=args.max_attempts)
        path = args.data_dir / "kbeauty" / cc / f"{doc['date']}.json"
        result = write_snapshot(path, doc)
        summary.append((cc, doc["status"], len(doc["items"]), result))
        print(f"[{cc}] → {doc['status']} ({len(doc['items'])}개) {path.relative_to(args.data_dir.parent)} {result}",
              flush=True)

    print("\n국가 | 상태 | 제품 수 | 저장")
    for row in summary:
        print(" | ".join(map(str, row)))
    # 한 국가라도 받았으면 성공으로 끝낸다. 실패 여부는 스냅샷과 사이트에 표시된다.
    return 0 if any(s in ("ok", "partial") for _, s, _, _ in summary) else 1


if __name__ == "__main__":
    sys.exit(main())

