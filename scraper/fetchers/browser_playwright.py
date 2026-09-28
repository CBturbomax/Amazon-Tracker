"""방식 3: Playwright(Chromium). 스크롤해서 lazy-load되는 나머지 제품까지 불러온다."""

from __future__ import annotations

import os
import random
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from scraper.fetchers.base import DEFAULT_ACCEPT_LANGUAGE, FetchResult, now_kst

ITEM_SELECTOR = "#gridItemRoot"


class PlaywrightFetcher:
    name = "playwright"

    def __init__(self, timeout: float = 45.0, headless: bool = True, target_items: int = 50,
                 accept_language: str = DEFAULT_ACCEPT_LANGUAGE) -> None:
        self.timeout_ms = int(timeout * 1000)
        self.target_items = target_items
        self._pw = sync_playwright().start()
        launch_kwargs: dict = {"headless": headless}
        # 설치된 Chromium을 직접 지정하고 싶을 때 (예: 사내 PC)
        if os.environ.get("CHROMIUM_PATH"):
            launch_kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]
        self._browser = self._pw.chromium.launch(**launch_kwargs)
        # 헤드리스 기본 UA에는 "HeadlessChrome"이 들어가므로 실제 엔진 버전으로 일반 UA를 만든다.
        major = self._browser.version.split(".")[0]
        ua = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")
        self._context = self._browser.new_context(
            user_agent=ua,
            locale=accept_language.split(",")[0],
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": accept_language},
        )
        self._page = self._context.new_page()

    def fetch(self, url: str) -> FetchResult:
        fetched_at = now_kst().isoformat(timespec="seconds")
        t0 = time.monotonic()
        page = self._page
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            status = resp.status if resp else None
            self._scroll_until_loaded()
            html = page.content()
        except PlaywrightError as e:
            return FetchResult(url, self.name, fetched_at, elapsed_s=round(time.monotonic() - t0, 2),
                               error=f"{type(e).__name__}: {str(e).splitlines()[0]}")
        return FetchResult(url, self.name, fetched_at, status=status, final_url=page.url,
                           elapsed_s=round(time.monotonic() - t0, 2), html=html)

    def _scroll_until_loaded(self, max_rounds: int = 25, stable_rounds: int = 3) -> None:
        """제품 카드가 target_items개가 되거나, 몇 번 스크롤해도 늘지 않으면 멈춘다."""
        page = self._page
        last, stable = -1, 0
        for _ in range(max_rounds):
            count = page.locator(ITEM_SELECTOR).count()
            if count >= self.target_items:
                return
            if count == last:
                stable += 1
                if stable >= stable_rounds:
                    return
            else:
                stable = 0
            last = count
            page.mouse.wheel(0, random.randint(1200, 1800))
            page.wait_for_timeout(random.randint(600, 1200))

    def close(self) -> None:
        for closer in (self._context.close, self._browser.close, self._pw.stop):
            try:
                closer()
            except Exception:
                pass
