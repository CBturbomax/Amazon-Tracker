"""config/brands.json으로 제품명 → 회사를 찾는다."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

BRANDS_PATH = Path(__file__).resolve().parents[1] / "config" / "brands.json"


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    patterns: tuple[re.Pattern, ...]


def load_companies(path: Path = BRANDS_PATH) -> list[Company]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [Company(c["id"], c["name"], tuple(re.compile(p, re.IGNORECASE) for p in c["patterns"]))
            for c in doc["companies"]]


def match_company(title: str | None, companies: list[Company]) -> Company | None:
    if not title:
        return None
    for c in companies:
        if any(p.search(title) for p in c.patterns):
            return c
    return None
