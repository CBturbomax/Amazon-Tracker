import json
from pathlib import Path

from build.brands import BrandResolver, build_brands, norm_key

ALIASES = json.loads((Path(__file__).resolve().parents[1] / "config" / "brand_aliases.json").read_text())


def test_norm_and_aliases():
    r = BrandResolver(ALIASES, {})
    assert norm_key("L’Oréal Paris") == norm_key("L'Oreal Paris") == "lorealparis"
    assert r.canonical("L'Oreal Paris") == "L'Oréal Paris"
    assert r.canonical("Maybelline") == "Maybelline New York"
    assert r.canonical("Dr. Althea") == "Dr.Althea"
    assert r.canonical("medicube") == "Medicube"


def test_title_prefix_fallback():
    r = BrandResolver(ALIASES, {})
    assert r.from_title("La Roche-Posay Effaclar Duo+") == "La Roche-Posay"
    assert r.from_title("e.l.f. Instant Lift Brow Pencil") == "e.l.f."
    assert r.from_title("Dr.Althea 345 Relief Cream") == "Dr.Althea"
    assert r.from_title("Effaclar Duo+M") is None


def test_unknown_brand_uses_most_common_spelling():
    r = BrandResolver(ALIASES, {"A": {"brand": "Tree Hut"}, "B": {"brand": "TREE HUT"}, "C": {"brand": "Tree Hut"}})
    keys = {r.for_item({"asin": a, "title": ""}) for a in "ABC"}
    assert len(keys) == 1 and r.display(keys.pop()) == "Tree Hut"


def test_build_counts_zero_vs_null_and_capture():
    snaps = {"2026-09-28": {
        "US": {"status": "ok", "items": [{"asin": "A1", "title": "medicube pad", "rank": 1},
                                           {"asin": "A2", "title": "CeraVe cream", "rank": 2},
                                           {"asin": "A3", "title": "Mystery thing", "rank": 3}]},
        "UK": {"status": "ok", "items": [{"asin": "A1", "title": "medicube pad", "rank": 5}]},
        "DE": {"status": "failed", "items": []},
    }}
    imported = [{"source": "cap", "points": [{"date": "2026-09-21", "brands": [
        {"brand": "Medicube", "counts": {"US": 6, "UK": 11, "FR": 13, "DE": 6, "IT": 12, "ES": 16}, "total": 64},
        {"brand": "L'Oreal", "counts": {"US": 1, "UK": 0, "FR": 0, "DE": 0, "IT": 0, "ES": 0}, "total": 1},
        {"brand": "L'Oréal Paris", "counts": {"US": 4, "UK": 5, "FR": 7, "DE": 2, "IT": 7, "ES": 5}, "total": 30}]}]}]
    out = build_brands(snaps, imported, BrandResolver(ALIASES, {}))
    assert [p["date"] for p in out["points"]] == ["2026-09-21", "2026-09-28"]
    assert [p["source"] for p in out["points"]] == ["capture", "auto"]
    med = out["series"]["Medicube"]["values"]
    assert med["total"] == [64, 2] and med["US"] == [6, 1] and med["DE"] == [6, None]
    cv = out["series"]["CeraVe"]["values"]
    assert cv["US"] == [None, 1] and cv["UK"] == [None, 0]  # 수집한 나라에서 없으면 0, 캡처에 없으면 null
    assert out["series"]["L'Oréal Paris"]["values"]["total"][0] == 31  # 표기가 다른 이름은 합친다
    assert out["unresolved"][0]["by_country"] == {"US": 1, "UK": 0}
    assert out["ranks"]["total"][1][0] == {"b": "Medicube", "v": 2}
    assert out["series"]["Medicube"]["ranks"]["total"] == [1, 1]
