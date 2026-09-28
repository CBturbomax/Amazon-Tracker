import json

from build.build_site import build_kbeauty, build_meta, load_snapshots
from scraper.brands import load_companies

C = load_companies()


def snap(cc, date, items, status="ok"):
    return {"country": cc, "date": date, "collected_at": f"{date}T09:07:00+09:00", "status": status,
            "items": [{"rank": r, "asin": a, "title": t} for r, a, t in items]}


def write(tmp_path, s):
    p = tmp_path / "kbeauty" / s["country"] / f"{s['date']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(s))


def test_counts_deltas_new_out(tmp_path):
    write(tmp_path, snap("US", "2026-09-27", [(1, "A1", "medicube Zero Pore Pad"), (5, "A2", "COSRX Snail"),
                                               (9, "X", "CeraVe Cream")]))
    write(tmp_path, snap("US", "2026-09-28", [(2, "A1", "medicube Zero Pore Pad"), (7, "A3", "Anua Toner"),
                                               (8, "A4", "medicube Collagen")]))
    write(tmp_path, snap("UK", "2026-09-28", [(1, "A1", "medicube Zero Pore Pad")]))
    # 실패 기록 파일은 무시돼야 한다
    (tmp_path / "kbeauty" / "UK" / "2026-09-28.attempt-090000.json").write_text("{}")
    write(tmp_path, snap("DE", "2026-09-28", [], status="failed"))

    kb = build_kbeauty(load_snapshots(tmp_path), C, {})
    assert kb["dates"] == ["2026-09-27", "2026-09-28"]
    us = kb["days"]["2026-09-28"]["countries"]["US"]
    assert us["counts"] == {"apr": 2, "dalba": 0, "cosrx": 0, "anua": 1, "joseon": 0}
    assert us["delta"]["apr"] == 1 and us["delta"]["cosrx"] == -1
    assert us["total"] == 3 and us["total_delta"] == 1
    pad = "A1"
    assert us["new"] == ["A3", "A4"]
    assert us["out"] == [{"key": "A2", "prev_rank": 5}]
    assert us["prev_ranks"] == {pad: 1}
    uk = kb["days"]["2026-09-28"]["countries"]["UK"]
    assert uk["delta"] is None and uk["new"] == []  # 전날 데이터 없음
    assert "counts" not in kb["days"]["2026-09-28"]["countries"]["DE"]
    assert kb["days"]["2026-09-28"]["company_totals"]["apr"] == 3
    assert kb["series"]["US"]["apr"] == [1, 2]
    assert kb["series"]["UK"]["apr"] == [None, 1]
    # 같은 ASIN이면 국가가 달라도 한 제품
    assert kb["products"][pad]["ranks"]["US"] == [1, 2]
    assert kb["products"][pad]["ranks"]["UK"] == [None, 1]
    assert kb["products"][pad]["asins"] == {"US": "A1", "UK": "A1"}

    meta = build_meta(load_snapshots(tmp_path))
    st = {c["cc"]: c["status"] for c in meta["countries"]}
    assert st == {"US": "ok", "UK": "ok", "DE": "failed", "FR": "missing", "ES": "missing"}


def test_products_json_groups_asins_and_names(tmp_path):
    write(tmp_path, snap("US", "2026-09-28", [(2, "A1", "medicube Zero Pore Pad 2.0")]))
    write(tmp_path, snap("UK", "2026-09-28", [(1, "B1", "medicube Zero Pore Pads")]))
    prod = {"id": "zero-pore-pad", "name_ko": "제로모공패드", "company": "apr", "asins": ["A1", "B1"],
            "needs_review": False}
    kb = build_kbeauty(load_snapshots(tmp_path), C, {"A1": prod, "B1": prod})
    p = kb["products"]["zero-pore-pad"]
    assert p["name"] == "제로모공패드" and p["asins"] == {"US": "A1", "UK": "B1"}
    assert kb["days"]["2026-09-28"]["countries"]["US"]["ranks"] == {"zero-pore-pad": 2}
