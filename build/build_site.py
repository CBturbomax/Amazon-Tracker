"""원자료 스냅샷 → docs/data/*.json (사이트는 이 JSON만 읽는다).

    python -m build.build_site

만드는 파일
- docs/data/meta.json     마지막 수집 시각, 국가별 수집 성공/실패
- docs/data/kbeauty.json  탭 1·2용: 날짜별 회사×국가 제품 수, 증감, 신규/이탈, 제품별 순위 추이

모든 숫자는 여기서 원자료로 계산한다. 페이지는 고르고 그리기만 한다 (원칙 1·6).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from scraper.brands import load_companies, match_company
from scraper.fetchers.base import now_kst
from scraper.markets import MARKETS

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")  # .attempt-*.json(실패 기록)은 제외
USABLE = ("ok", "partial")


def load_snapshots(data_dir: Path) -> dict[str, dict[str, dict]]:
    """{date: {country: snapshot}}"""
    out: dict[str, dict[str, dict]] = {}
    for cc in MARKETS:
        d = data_dir / "kbeauty" / cc
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if SNAPSHOT_RE.match(p.name):
                snap = json.loads(p.read_text(encoding="utf-8"))
                out.setdefault(snap["date"], {})[cc] = snap
    return out


def load_products(path: Path) -> dict[str, dict]:
    """ASIN → 제품 정보"""
    doc = json.loads(path.read_text(encoding="utf-8"))
    by_asin: dict[str, dict] = {}
    for prod in doc.get("products", []):
        for asin in prod.get("asins", []):
            by_asin[asin] = prod
    return by_asin


def build_kbeauty(snaps: dict[str, dict[str, dict]], companies, products_by_asin: dict[str, dict]) -> dict:
    dates = sorted(snaps)
    company_ids = [c.id for c in companies]
    company_by_id = {c.id: c for c in companies}
    products: dict[str, dict] = {}
    days: dict[str, dict] = {}
    prev_by_cc: dict[str, dict] = {}  # 국가별 직전 사용 가능 날짜의 결과

    for date in dates:
        day: dict[str, dict] = {}
        for cc in MARKETS:
            snap = snaps[date].get(cc)
            if snap is None:
                continue
            entry = {"status": snap["status"], "collected_at": snap["collected_at"],
                     "items": len(snap.get("items", []))}
            if snap["status"] not in USABLE:
                day[cc] = entry
                continue

            counts = {cid: 0 for cid in company_ids}
            ranks: dict[str, int] = {}
            for it in snap["items"]:
                prod = products_by_asin.get(it["asin"])
                cid = prod.get("company") if prod else None
                if cid not in company_by_id:
                    c = match_company(it.get("title"), companies)
                    cid = c.id if c else None
                if cid is None or it.get("rank") is None:
                    continue
                counts[cid] += 1
                key = prod["id"] if prod else auto_key(cid, it.get("title"), it["asin"])
                info = products.setdefault(key, {
                    "name": (prod or {}).get("name_ko") or it.get("title") or it["asin"],
                    "name_en": it.get("title"),
                    "company": cid,
                    "needs_review": bool(prod.get("needs_review", True)) if prod else True,
                    "registered": prod is not None,
                    "asins": {},
                })
                info["asins"][cc] = it["asin"]
                if not info["registered"] and it.get("title"):
                    info["name"] = info["name_en"] = it["title"]  # 미등록이면 최신 영문명
                ranks[key] = min(ranks.get(key, 10**6), it["rank"])

            prev = prev_by_cc.get(cc)
            total = sum(counts.values())
            entry.update({
                "counts": counts,
                "total": total,
                "delta": {cid: counts[cid] - prev["counts"][cid] for cid in company_ids} if prev else None,
                "total_delta": total - prev["total"] if prev else None,
                "prev_date": prev["date"] if prev else None,
                "ranks": ranks,
                "prev_ranks": {k: prev["ranks"][k] for k in ranks if prev and k in prev["ranks"]},
                "new": sorted((k for k in ranks if prev and k not in prev["ranks"]), key=ranks.get),
                "out": sorted(({"key": k, "prev_rank": r} for k, r in prev["ranks"].items() if k not in ranks),
                              key=lambda x: x["prev_rank"]) if prev else [],
            })
            prev_by_cc[cc] = {"date": date, "counts": counts, "total": total, "ranks": ranks}
            day[cc] = entry

        # 국가 합계 (사용 가능한 국가만)
        usable = [e for e in day.values() if "counts" in e]
        day_totals = {cid: sum(e["counts"][cid] for e in usable) for cid in company_ids}
        deltas = [e["delta"] for e in usable if e["delta"] is not None]
        totals_delta = {cid: sum(d[cid] for d in deltas) for cid in company_ids} if deltas else None
        days[date] = {
            "countries": day,
            "company_totals": day_totals,
            "grand_total": sum(day_totals.values()),
            "company_totals_delta": totals_delta,
            "grand_total_delta": sum(totals_delta.values()) if totals_delta else None,
            "company_products": _company_products(day, products, company_ids),
        }
        days[date]["summary"] = _summary(days[date], company_by_id)

    # 추이 차트용 시계열 (dates 순서, 수집 못 한 날은 null)
    series = {cc: {cid: [days[d]["countries"].get(cc, {}).get("counts", {}).get(cid) for d in dates]
                   for cid in company_ids} for cc in MARKETS}
    series_total = {cc: [days[d]["countries"].get(cc, {}).get("total") for d in dates] for cc in MARKETS}
    for key, info in products.items():
        info["short"] = info["name"] if info["registered"] else short_title(info["name"])
        info["ranks"] = {cc: [days[d]["countries"].get(cc, {}).get("ranks", {}).get(key) for d in dates]
                         for cc in MARKETS}

    return {
        "companies": [{"id": c.id, "name": c.name} for c in companies],
        "countries": [{"cc": cc, "name": m["name"], "domain": m["domain"]} for cc, m in MARKETS.items()],
        "dates": dates,
        "latest_date": dates[-1] if dates else None,
        "days": days,
        "series": series,
        "series_total": series_total,
        "products": products,
    }


def _company_products(day: dict, products: dict, company_ids: list[str]) -> dict[str, list[dict]]:
    """회사별 제품 목록: 국가별 순위와 전일 순위. 가장 좋은 순위 순."""
    by_key: dict[str, dict] = {}
    for cc, e in day.items():
        for key, rank in e.get("ranks", {}).items():
            row = by_key.setdefault(key, {"key": key, "ranks": {}, "prev": {}, "best": rank})
            row["ranks"][cc] = rank
            if key in e["prev_ranks"]:
                row["prev"][cc] = e["prev_ranks"][key]
            row["best"] = min(row["best"], rank)
    out: dict[str, list[dict]] = {cid: [] for cid in company_ids}
    for row in sorted(by_key.values(), key=lambda r: (r["best"], -len(r["ranks"]))):
        out[products[row["key"]]["company"]].append(row)
    return out


def _summary(d: dict, company_by_id: dict) -> list[str]:
    """1~3줄 요약. 숫자는 모두 위에서 계산한 값이다."""
    lines: list[str] = []
    usable = {cc: e for cc, e in d["countries"].items() if "counts" in e}
    if not usable:
        return ["수집된 국가가 없습니다."]
    n = len(usable)
    total = d["grand_total"]
    delta = d["grand_total_delta"]
    change = "" if delta is None else (" (전일과 같음)" if delta == 0 else f" (전일 대비 {delta:+d})")
    lines.append(f"{n}개국 Top 100 안의 K뷰티 제품은 모두 {total}개{change}.")
    top = max(d["company_totals"].items(), key=lambda kv: kv[1])
    if top[1] > 0:
        lines.append(f"가장 많은 회사는 {company_by_id[top[0]].name} ({top[1]}개).")
    new = sum(len(e["new"]) for e in usable.values())
    out = sum(len(e["out"]) for e in usable.values())
    if any(e["prev_date"] for e in usable.values()):
        lines.append(f"새로 들어온 제품 {new}개, 빠진 제품 {out}개.")
    return lines


def auto_key(company_id: str, title: str | None, asin: str) -> str:
    """products.json에 없는 제품의 묶음 키.

    국가별 ASIN이 달라도 제품명 앞부분이 같으면 같은 제품으로 본다.
    잘못 묶이면 products.json에 등록해서 바로잡는다.
    """
    if not title:
        return asin
    norm = re.sub(r"[^0-9a-z]+", "-", short_title(title).lower().replace("’", "'")).strip("-")
    return f"auto:{company_id}:{norm}" if norm else asin


def short_title(title: str, limit: int = 60) -> str:
    """영문 제품명을 앞부분만 남긴다 (미등록 제품 표시용)."""
    t = re.split(r"\s[-–|]\s|,\s|\s\(", title, maxsplit=1)[0].strip()
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + "…"


def build_meta(snaps: dict[str, dict[str, dict]]) -> dict:
    latest = max(snaps) if snaps else None
    countries = []
    for cc, m in MARKETS.items():
        snap = snaps.get(latest, {}).get(cc) if latest else None
        countries.append({
            "cc": cc, "name": m["name"],
            "status": snap["status"] if snap else "missing",
            "collected_at": snap["collected_at"] if snap else None,
            "items": len(snap["items"]) if snap else 0,
        })
    collected = [c["collected_at"] for c in countries if c["collected_at"]]
    return {"latest_date": latest, "last_collected_at": max(collected) if collected else None,
            "countries": countries}


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="원자료 → docs/data/*.json")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    ap.add_argument("--config-dir", type=Path, default=ROOT / "config")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "data")
    args = ap.parse_args(argv)

    snaps = load_snapshots(args.data_dir)
    companies = load_companies(args.config_dir / "brands.json")
    products = load_products(args.config_dir / "products.json")
    generated_at = now_kst().isoformat(timespec="seconds")

    kb = build_kbeauty(snaps, companies, products)
    meta = build_meta(snaps)
    write_json(args.out / "kbeauty.json", {"generated_at": generated_at, **kb})
    write_json(args.out / "meta.json", {"generated_at": generated_at, **meta})
    print(f"빌드 완료: {len(kb['dates'])}일, K뷰티 제품 {len(kb['products'])}개 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
