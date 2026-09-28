"""1단계 차단 테스트.

미국 베스트셀러 페이지를 requests / curl_cffi / Playwright 방식으로 수집해서
방식별 성공·CAPTCHA·503 비율과 페이지당 파싱 제품 수를 표로 출력한다.

    python -m tools.block_test                          # 3방식 x 20페이지
    python -m tools.block_test --methods curl_cffi --limit 5
    python -m tools.block_test --label company-pc --shuffle

결과: reports/block_test/{KST시각}_{label}/ 아래 results.json, summary.md, html/
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
from scraper.parse_bestsellers import ParseResult, parse_bestseller_page
from tools.block_test_report import render_markdown, write_step_summary

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="아마존 베스트셀러 차단 테스트")
    ap.add_argument("--methods", default=",".join(METHODS),
                    help=f"쉼표로 구분 (기본: {','.join(METHODS)})")
    ap.add_argument("--urls", type=Path, default=ROOT / "config" / "block_test_urls.json")
    ap.add_argument("--limit", type=int, default=20, help="방식마다 요청할 페이지 수 (기본 20)")
    ap.add_argument("--delay-min", type=float, default=3.0)
    ap.add_argument("--delay-max", type=float, default=8.0)
    ap.add_argument("--cooldown", type=float, default=30.0, help="방식 사이 쉬는 시간(초)")
    ap.add_argument("--stop-after", type=int, default=3,
                    help="연속 차단(CAPTCHA/503)이 이 횟수면 그 방식을 멈춘다 (0 = 끝까지)")
    ap.add_argument("--shuffle", action="store_true", help="방식마다 페이지 순서를 섞는다")
    ap.add_argument("--label", default="local", help="환경 이름 (예: local, company-pc, actions)")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "block_test")
    ap.add_argument("--save-html", choices=("none", "failures", "all"), default="failures",
                    help="HTML 저장 범위 (failures = 실패 전부 + 방식별 성공 1개)")
    ap.add_argument("--headed", action="store_true", help="Playwright를 창을 띄워 실행")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv)
    args.methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    bad = [m for m in args.methods if m not in METHODS]
    if bad:
        ap.error(f"알 수 없는 방식: {', '.join(bad)}")
    if args.delay_min > args.delay_max:
        ap.error("--delay-min이 --delay-max보다 큽니다")
    return args


def load_pages(path: Path, limit: int) -> list[dict]:
    pages = json.loads(path.read_text(encoding="utf-8"))["pages"]
    return pages[:limit]


def run_method(method: str, pages: list[dict], args: argparse.Namespace, run_dir: Path,
               rng: random.Random) -> list[dict]:
    order = list(pages)
    if args.shuffle:
        rng.shuffle(order)

    kwargs = {"headless": not args.headed} if method == "playwright" else {}
    records: list[dict] = []
    try:
        fetcher = make_fetcher(method, **kwargs)
    except Exception as e:
        # 라이브러리·브라우저가 없어서 시작조차 못 한 경우도 결과에 남긴다
        print(f"[{method}] 시작 실패: {type(e).__name__}: {e}", flush=True)
        for p in order:
            records.append(_record(args.label, method, p, None, ParseResult(), "error",
                                   error=f"init: {type(e).__name__}: {e}"))
        return records

    consecutive_blocks = 0
    saved_ok_sample = False
    try:
        for i, page in enumerate(order):
            if i > 0:
                time.sleep(rng.uniform(args.delay_min, args.delay_max))
            fr = fetcher.fetch(page["url"])
            parsed = parse_bestseller_page(fr.html) if fr.html and not fr.block else ParseResult()
            outcome = classify(fr.status, fr.block, fr.error, parsed.rendered_count)
            rec = _record(args.label, method, page, fr, parsed, outcome)
            records.append(rec)
            print(f"[{method}] {i + 1:>2}/{len(order)} {page['id']:<22} {outcome:<10} "
                  f"status={fr.status} cards={parsed.rendered_count} recs={parsed.recs_count} "
                  f"{fr.elapsed_s}s" + (f" err={fr.error}" if fr.error else ""), flush=True)

            want_html = (args.save_html == "all"
                         or (args.save_html == "failures" and (outcome != "ok" or not saved_ok_sample)))
            if want_html and fr.html:
                html_dir = run_dir / "html"
                html_dir.mkdir(parents=True, exist_ok=True)
                (html_dir / f"{method}_{page['id']}_{outcome}.html").write_text(fr.html, encoding="utf-8")
                saved_ok_sample = saved_ok_sample or outcome == "ok"

            consecutive_blocks = consecutive_blocks + 1 if outcome in ("captcha", "http_503") else 0
            if args.stop_after and consecutive_blocks >= args.stop_after:
                rest = order[i + 1:]
                print(f"[{method}] 연속 차단 {consecutive_blocks}회 → 중단 (남은 {len(rest)}페이지 skipped)",
                      flush=True)
                records.extend(_record(args.label, method, p, None, ParseResult(), "skipped") for p in rest)
                break
    finally:
        fetcher.close()
    return records


def _record(label: str, method: str, page: dict, fr, parsed: ParseResult, outcome: str,
            error: str | None = None) -> dict:
    meta = fr.meta() if fr else {}
    return {
        "label": label,
        "method": method,
        "page_id": page["id"],
        "category": page.get("category"),
        "url": page["url"],
        "outcome": outcome,
        "status": meta.get("status"),
        "final_url": meta.get("final_url"),
        "fetched_at": meta.get("fetched_at"),
        "elapsed_s": meta.get("elapsed_s", 0.0),
        "html_bytes": meta.get("html_bytes", 0),
        "error": error or meta.get("error"),
        "rendered_count": parsed.rendered_count,
        "recs_count": parsed.recs_count,
        # 파싱이 제대로 되는지 눈으로 확인할 수 있게 앞의 3개만 남긴다
        "sample_items": parsed.items[:3],
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔
    except (AttributeError, ValueError):
        pass
    args = parse_args(argv)
    rng = random.Random(args.seed)
    pages = load_pages(args.urls, args.limit)
    started = now_kst()
    run_dir = args.out / f"{started.strftime('%Y%m%d-%H%M%S')}_{args.label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"차단 테스트 시작 {started.isoformat(timespec='seconds')} | 방식 {args.methods} | "
          f"{len(pages)}페이지 | 딜레이 {args.delay_min}~{args.delay_max}s | 결과 {run_dir}", flush=True)

    records: list[dict] = []
    for j, method in enumerate(args.methods):
        if j > 0 and args.cooldown > 0:
            print(f"--- 다음 방식 전 {args.cooldown:.0f}초 대기 ---", flush=True)
            time.sleep(args.cooldown)
        records.extend(run_method(method, pages, args, run_dir, rng))

    result = {
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": now_kst().isoformat(timespec="seconds"),
        "label": args.label,
        "settings": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "records": records,
    }
    (run_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_markdown(records, title=f"차단 테스트 결과 — {args.label} ({result['started_at']} KST)")
    (run_dir / "summary.md").write_text(md + "\n", encoding="utf-8")
    print("\n" + md)
    write_step_summary(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
