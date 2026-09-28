"""방식 2: curl_cffi (Chrome TLS/HTTP2 지문 임퍼소네이션)."""

from __future__ import annotations

import time

from curl_cffi import requests as cffi_requests

from scraper.fetchers.base import DEFAULT_ACCEPT_LANGUAGE, FetchResult, now_kst


class CurlCffiFetcher:
    name = "curl_cffi"

    def __init__(self, timeout: float = 30.0, impersonate: str = "chrome",
                 accept_language: str = DEFAULT_ACCEPT_LANGUAGE) -> None:
        self.timeout = timeout
        # User-Agent 등 브라우저 헤더는 impersonate가 지문과 맞게 채운다.
        self.session = cffi_requests.Session(impersonate=impersonate)
        self.session.headers.update({"Accept-Language": accept_language})

    def fetch(self, url: str) -> FetchResult:
        fetched_at = now_kst().isoformat(timespec="seconds")
        t0 = time.monotonic()
        try:
            r = self.session.get(url, timeout=self.timeout)
        except Exception as e:  # curl_cffi는 여러 종류의 예외를 던진다
            return FetchResult(url, self.name, fetched_at, elapsed_s=round(time.monotonic() - t0, 2),
                               error=f"{type(e).__name__}: {e}")
        return FetchResult(url, self.name, fetched_at, status=r.status_code, final_url=str(r.url),
                           elapsed_s=round(time.monotonic() - t0, 2), html=r.text)

    def close(self) -> None:
        self.session.close()
