import json

from scraper.snapshot import write_snapshot


def test_never_overwrites_ok(tmp_path):
    p = tmp_path / "US" / "2026-09-28.json"
    assert write_snapshot(p, {"status": "ok", "v": 1, "collected_at": "2026-09-28T09:00:00+09:00"}) == "written"
    assert write_snapshot(p, {"status": "ok", "v": 2}) == "kept_existing"
    assert json.loads(p.read_text())["v"] == 1


def test_failed_snapshot_is_preserved_on_retry(tmp_path):
    p = tmp_path / "2026-09-28.json"
    write_snapshot(p, {"status": "failed", "v": 1, "collected_at": "2026-09-28T09:00:05+09:00"})
    assert write_snapshot(p, {"status": "ok", "v": 2}) == "written"
    assert json.loads(p.read_text())["v"] == 2
    assert json.loads((tmp_path / "2026-09-28.attempt-090005.json").read_text())["v"] == 1
