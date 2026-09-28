"""차단 테스트 결과 표 만들기.

단독 실행하면 여러 results.json(예: Actions에서 방식별로 나눠 돈 결과)을 합쳐 표 하나로 출력한다.

    python -m tools.block_test_report reports/block_test/*/results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

FULL_PAGE = 50


def summarize(records: list[dict]) -> list[dict]:
    """(환경, 방식)별 집계."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        groups.setdefault((r["label"], r["method"]), []).append(r)
    rows = []
    for (label, method), rs in groups.items():
        attempted = [r for r in rs if r["outcome"] != "skipped"]
        ok = [r for r in attempted if r["outcome"] == "ok"]
        n = len(attempted)
        count = lambda o: sum(1 for r in attempted if r["outcome"] == o)  # noqa: E731
        rows.append({
            "label": label,
            "method": method,
            "attempted": n,
            "ok": len(ok),
            "captcha": count("captcha"),
            "http_503": count("http_503"),
            "other": n - len(ok) - count("captcha") - count("http_503"),
            "skipped": len(rs) - n,
            "ok_rate": round(100 * len(ok) / n) if n else 0,
            "captcha_rate": round(100 * count("captcha") / n) if n else 0,
            "http_503_rate": round(100 * count("http_503") / n) if n else 0,
            "avg_rendered": _avg([r["rendered_count"] for r in ok]),
            "min_rendered": min((r["rendered_count"] for r in ok), default=0),
            "avg_recs": _avg([r["recs_count"] for r in ok]),
            "full_pages": sum(1 for r in ok if r["rendered_count"] >= FULL_PAGE),
            "full_recs_pages": sum(1 for r in ok if r["recs_count"] >= FULL_PAGE),
            "avg_elapsed_s": round(sum(r["elapsed_s"] for r in attempted) / n, 1) if n else 0.0,
        })
    return rows


def _avg(xs: list[int]) -> float:
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def summary_table(rows: list[dict]) -> str:
    head = ("| 환경 | 방식 | 요청 | 성공 | CAPTCHA | 503 | 기타 | 중단 | 성공률 | CAPTCHA율 | 503율 "
            "| 파싱 평균(최소) | 50개 완전 | ASIN목록 평균 | ASIN목록 50개 | 평균 응답(초) |")
    sep = "|" + "---|" * 16
    lines = [head, sep]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['method']} | {r['attempted']} | {r['ok']} | {r['captcha']} | {r['http_503']} "
            f"| {r['other']} | {r['skipped']} | {r['ok_rate']}% | {r['captcha_rate']}% | {r['http_503_rate']}% "
            f"| {r['avg_rendered']} ({r['min_rendered']}) | {r['full_pages']}/{r['ok']} | {r['avg_recs']} "
            f"| {r['full_recs_pages']}/{r['ok']} | {r['avg_elapsed_s']} |"
        )
    return "\n".join(lines)


def detail_table(records: list[dict]) -> str:
    """페이지 × 방식 결과. 칸에는 결과(파싱 카드 수/ASIN목록 수)."""
    cols = list(dict.fromkeys(f"{r['label']}:{r['method']}" for r in records))
    pages = list(dict.fromkeys(r["page_id"] for r in records))
    cell: dict[tuple[str, str], str] = {}
    for r in records:
        key = (r["page_id"], f"{r['label']}:{r['method']}")
        if r["outcome"] == "ok":
            cell[key] = f"ok {r['rendered_count']}/{r['recs_count']}"
        elif r["outcome"] in ("http_other", "error"):
            cell[key] = f"{r['outcome']} {r.get('status') or ''}".strip()
        else:
            cell[key] = r["outcome"]
    lines = ["| 페이지 | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for p in pages:
        lines.append(f"| {p} | " + " | ".join(cell.get((p, c), "-") for c in cols) + " |")
    return "\n".join(lines)


def render_markdown(records: list[dict], title: str = "차단 테스트 결과") -> str:
    return "\n\n".join([
        f"## {title}",
        summary_table(summarize(records)),
        "- 성공 = HTTP 200 + 차단 표식 없음 + 제품 1개 이상 파싱.\n"
        "- 파싱 = 렌더된 제품 카드 수 (순위·ASIN·제품명·가격·평점·평점 수).\n"
        "- ASIN목록 = 페이지 안 `data-client-recs-list`에 들어 있는 ASIN 수 (스크롤 없이 50개가 나오는지 확인용).\n"
        "- 중단 = 연속 차단으로 그 방식을 멈춰서 요청하지 않은 페이지.",
        "### 페이지별 (ok 파싱/ASIN목록)",
        detail_table(records),
    ])


def write_step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="여러 results.json을 합쳐 표로 출력")
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--step-summary", action="store_true", help="GITHUB_STEP_SUMMARY에도 쓴다")
    args = ap.parse_args(argv)
    records: list[dict] = []
    for p in args.results:
        records.extend(json.loads(p.read_text(encoding="utf-8"))["records"])
    md = render_markdown(records, title="차단 테스트 결과 (합계)")
    print(md)
    if args.step_summary:
        write_step_summary(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
