"""방식 1: requests + 일반 브라우저 헤더."""

from __future__ import annotations

import time

import requests

from scraper.fetchers.base import CHROME_UA, DEFAULT_ACCEPT_LANGUAGE, FetchResult, now_kst

HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": DEFAULT_ACCEPT_LANGUAGE,
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
}


class RequestsFetcher:
    name = "requests"

    def __init__(self, timeout: float = 30.0, accept_language: str = DEFAULT_ACCEPT_LANGUAGE) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({**HEADERS, "Accept-Language": accept_language})

    def fetch(self, url: str) -> FetchResult:
        fetched_at = now_kst().isoformat(timespec="seconds")
        t0 = time.monotonic()
        try:
            r = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            return FetchResult(url, self.name, fetched_at, elapsed_s=round(time.monotonic() - t0, 2),
                               error=f"{type(e).__name__}: {e}")
        return FetchResult(url, self.name, fetched_at, status=r.status_code, final_url=r.url,
                           elapsed_s=round(time.monotonic() - t0, 2), html=r.text)

    def close(self) -> None:
        self.session.close()
