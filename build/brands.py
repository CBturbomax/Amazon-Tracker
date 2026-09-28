"""브랜드 랭킹 (탭 "브랜드 랭킹") 데이터.

시점마다, 나라마다 "Top 100 안에 그 브랜드 제품이 몇 개인가"를 센다.
- 자동 수집 시점: data/kbeauty/{CC}/{date}.json + data/asin_brands.json(ASIN → 브랜드)
- 과거 시점: data/imported/*.json (사용자 제공 캡처 집계표, 원본 값 그대로)

브랜드명은 config/brand_aliases.json으로 통일한다.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from scraper.markets import MARKETS

# 레퍼런스(캡처 표)와 같은 나라 순서
COUNTRY_ORDER = ["US", "UK", "FR", "DE", "IT", "ES"]
TOTAL = "total"
USABLE = ("ok", "partial")
MAX_PREFIX_TOKENS = 4


def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s.replace("’", "'")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return s.split()


def norm_key(s: str) -> str:
    return "".join(_tokens(s))


class BrandResolver:
    def __init__(self, aliases_doc: dict, asin_brands: dict[str, dict]):
        self.map: dict[str, str] = {}
        for canon, alist in aliases_doc.get("aliases", {}).items():
            for a in [canon, *alist]:
                self.map[norm_key(a)] = canon
        self.kbeauty = aliases_doc.get("kbeauty", [])
        self.asin_brands = asin_brands
        self.spellings: dict[str, Counter] = defaultdict(Counter)  # 별칭 없는 브랜드의 표기
        # 상세 페이지로 확인한 브랜드명도 제품명 앞부분 매칭에 쓴다 (별칭이 우선)
        self.learned: dict[str, str] = {}
        for rec in asin_brands.values():
            b = rec.get("brand")
            if b and len(norm_key(b)) >= 3 and norm_key(b) not in self.map:
                self.learned[norm_key(b)] = self.canonical(b)

    def canonical(self, raw: str) -> str:
        key = norm_key(raw)
        if key in self.map:
            return self.map[key]
        self.spellings[key][raw.strip()] += 1
        return "key:" + key  # 표시 이름은 finalize()에서 가장 흔한 표기로 정한다

    def from_title(self, title: str) -> str | None:
        """상세 페이지 브랜드가 아직 없을 때: 제품명 앞부분이 알려진 브랜드면 그 브랜드."""
        toks = _tokens(title or "")
        for k in range(min(MAX_PREFIX_TOKENS, len(toks)), 0, -1):
            key = "".join(toks[:k])
            if key in self.map:
                return self.map[key]
            if key in self.learned:
                return self.learned[key]
        return None

    def for_item(self, item: dict) -> str | None:
        rec = self.asin_brands.get(item["asin"]) or {}
        if rec.get("brand"):
            return self.canonical(rec["brand"])
        return self.from_title(item.get("title") or "")

    def display(self, b: str) -> str:
        if b.startswith("key:"):
            sp = self.spellings.get(b[4:])
            return sp.most_common(1)[0][0] if sp else b[4:]
        return b


def build_brands(snaps: dict[str, dict[str, dict]], imported: list[dict], resolver: BrandResolver,
                 grid_rows: int = 15, keep_rank: int = 30) -> dict:
    points: list[dict] = []           # {"date", "source", "status": {cc: status}}
    values: list[dict[str, dict]] = []  # 시점별 {brand: {cc|total: n}}
    unresolved: list[dict] = []

    # 1) 과거 캡처 시점
    cap_dates = set()
    for doc in imported:
        for p in doc["points"]:
            v: dict[str, dict] = defaultdict(dict)
            for row in p["brands"]:
                b = resolver.canonical(row["brand"])
                for cc, n in row["counts"].items():
                    v[b][cc] = v[b].get(cc, 0) + n
                v[b][TOTAL] = v[b].get(TOTAL, 0) + row["total"]
            points.append({"date": p["date"], "source": "capture", "status": {}})
            values.append(dict(v))
            cap_dates.add(p["date"])

    # 2) 자동 수집 시점
    for date in sorted(snaps):
        if date in cap_dates:
            continue
        status = {cc: snaps[date][cc]["status"] if cc in snaps[date] else "missing" for cc in COUNTRY_ORDER}
        v: dict[str, dict] = defaultdict(dict)
        n_unres = {}
        usable = [cc for cc in COUNTRY_ORDER if status[cc] in USABLE]
        for cc in usable:
            miss = 0
            for it in snaps[date][cc]["items"]:
                b = resolver.for_item(it)
                if b is None:
                    miss += 1
                    continue
                v[b][cc] = v[b].get(cc, 0) + 1
            n_unres[cc] = miss
        for b in v:
            for cc in usable:
                v[b].setdefault(cc, 0)  # Top 100 전체를 봤으므로 없으면 0
            v[b][TOTAL] = sum(v[b][cc] for cc in usable)
        points.append({"date": date, "source": "auto", "status": status})
        values.append(dict(v))
        unresolved.append({"date": date, "by_country": n_unres})

    order = sorted(range(len(points)), key=lambda i: points[i]["date"])
    points = [points[i] for i in order]
    values = [values[i] for i in order]

    # 3) 시점·나라별 순위 (값 내림차순, 같으면 이름순)
    series_keys = [TOTAL, *COUNTRY_ORDER]
    ranks: dict[str, list[list[dict]]] = {k: [] for k in series_keys}
    rank_of: dict[str, dict[str, list]] = defaultdict(lambda: {k: [None] * len(points) for k in series_keys})
    kept: set[str] = {k["brand"] for k in resolver.kbeauty}
    for t, v in enumerate(values):
        for k in series_keys:
            lst = sorted(((b, x[k]) for b, x in v.items() if x.get(k)), key=lambda bx: (-bx[1], resolver.display(bx[0])))
            for r, (b, _) in enumerate(lst, 1):
                rank_of[b][k][t] = r
                if r <= keep_rank:
                    kept.add(b)
            ranks[k].append([{"b": resolver.display(b), "v": n} for b, n in lst[:grid_rows]])

    series = {}
    for b in sorted(kept, key=resolver.display):
        name = resolver.display(b)
        if not any(b in v for v in values):
            continue
        series[name] = {
            "values": {k: [values[t].get(b, {}).get(k) for t in range(len(points))] for k in series_keys},
            "ranks": dict(rank_of[b]) if b in rank_of else {k: [None] * len(points) for k in series_keys},
        }

    return {
        "countries": [{"cc": cc, "name": MARKETS[cc]["name"]} for cc in COUNTRY_ORDER],
        "points": points,
        "kbeauty": resolver.kbeauty,
        "ranks": ranks,
        "series": series,
        "unresolved": unresolved,
        "sources": [{"source": d["source"], "note": d.get("note"), "mismatches": d.get("total_mismatches", [])}
                    for d in imported],
    }


def load_imported(data_dir: Path) -> list[dict]:
    d = data_dir / "imported"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.is_dir() else []
