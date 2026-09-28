"""Fetcher 공통 인터페이스.

fetcher는 "URL → HTML + 메타(상태 코드, 차단 여부, 소요 시간)"만 책임진다.
파싱과 저장은 fetcher 밖에서 한다. 수집 방식(requests / curl_cffi / Playwright /
유료 API)은 이 인터페이스의 구현체로 교체한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from scraper.classify import detect_block

# KST는 서머타임이 없으므로 고정 오프셋을 쓴다 (Windows에서 tzdata 없이도 동작).
KST = timezone(timedelta(hours=9), name="KST")

# requests 방식에서 쓰는 일반 데스크톱 Chrome 헤더.
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def now_kst() -> datetime:
    return datetime.now(KST)


@dataclass
class FetchResult:
    url: str
    method: str
    fetched_at: str  # KST ISO 8601
    status: int | None = None
    final_url: str | None = None
    elapsed_s: float = 0.0
    html: str = field(default="", repr=False)
    error: str | None = None
    block: str | None = None  # "captcha" | "http_503" | None

    def __post_init__(self) -> None:
        if self.block is None and self.error is None:
            self.block = detect_block(self.status, self.html)

    def meta(self) -> dict:
        """HTML 본문을 뺀 메타 정보 (스냅샷·리포트 저장용)."""
        d = asdict(self)
        d.pop("html")
        d["html_bytes"] = len(self.html.encode("utf-8"))
        return d


class Fetcher(Protocol):
    name: str

    def fetch(self, url: str) -> FetchResult: ...

    def close(self) -> None: ...
