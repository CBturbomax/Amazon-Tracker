"""수집 방식별 fetcher. 필요한 라이브러리만 import되도록 지연 로딩한다."""

from __future__ import annotations

from scraper.fetchers.base import Fetcher, FetchResult

METHODS = ("requests", "curl_cffi", "playwright")


def make_fetcher(method: str, **kwargs) -> Fetcher:
    if method == "requests":
        from scraper.fetchers.http_requests import RequestsFetcher
        return RequestsFetcher(**kwargs)
    if method == "curl_cffi":
        from scraper.fetchers.http_curl_cffi import CurlCffiFetcher
        return CurlCffiFetcher(**kwargs)
    if method == "playwright":
        from scraper.fetchers.browser_playwright import PlaywrightFetcher
        return PlaywrightFetcher(**kwargs)
    raise ValueError(f"알 수 없는 수집 방식: {method} (가능: {', '.join(METHODS)})")


__all__ = ["METHODS", "Fetcher", "FetchResult", "make_fetcher"]
