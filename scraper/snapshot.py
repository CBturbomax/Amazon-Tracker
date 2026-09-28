"""원자료 스냅샷 저장.

원칙 5: 한 번 저장한 정상 스냅샷은 덮어쓰지 않는다.
같은 날 다시 수집하는 경우:
- 기존 파일이 status "ok"면 새 결과를 저장하지 않는다.
- 기존 파일이 "ok"가 아니면 기존 파일을 {date}.attempt-{HHMMSS}.json으로 옮겨 보존하고 새 결과를 쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def write_snapshot(path: Path, doc: dict) -> str:
    """스냅샷을 쓰고 "written" / "kept_existing"을 돌려준다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("status") == "ok":
            return "kept_existing"
        stamp = (old.get("collected_at") or "unknown")[11:19].replace(":", "")
        path.rename(path.with_name(f"{path.stem}.attempt-{stamp}.json"))
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return "written"
