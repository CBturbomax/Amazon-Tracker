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
            self._dismiss_cookie_banner()
            if not self._scroll_until_loaded():
                # 가끔 lazy-load가 안 붙는다. 맨 위로 갔다가 한 번 더 천천히 내린다 (새 요청 아님).
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)
                self._scroll_until_loaded(step=(600, 900), wait=(1200, 1800))
            html = page.content()
        except PlaywrightError as e:
            return FetchResult(url, self.name, fetched_at, elapsed_s=round(time.monotonic() - t0, 2),
                               error=f"{type(e).__name__}: {str(e).splitlines()[0]}")
        return FetchResult(url, self.name, fetched_at, status=status, final_url=page.url,
                           elapsed_s=round(time.monotonic() - t0, 2), html=html)

    def _dismiss_cookie_banner(self) -> None:
        """유럽 사이트의 쿠키 동의 배너를 닫는다 (없으면 그냥 넘어간다)."""
        btn = self._page.locator("#sp-cc-accept")
        try:
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=3000)
                self._page.wait_for_timeout(500)
        except PlaywrightError:
            pass

    def _expected_items(self) -> int:
        """페이지에 들어 있는 ASIN 목록 수 (49개인 카테고리도 있다). 못 찾으면 target_items."""
        n = self._page.evaluate(
            """() => { const el = document.querySelector('[data-client-recs-list]');
                       try { return el ? JSON.parse(el.getAttribute('data-client-recs-list')).length : 0; }
                       catch (e) { return 0; } }""")
        return min(n, self.target_items) if n else self.target_items

    def _scroll_until_loaded(self, max_rounds: int = 25, stable_rounds: int = 3,
                             step: tuple[int, int] = (1200, 1800),
                             wait: tuple[int, int] = (600, 1200)) -> bool:
        """제품 카드가 다 나오면 True. 몇 번 스크롤해도 늘지 않으면 False."""
        page = self._page
        target = self._expected_items()
        last, stable = -1, 0
        for _ in range(max_rounds):
            count = page.locator(ITEM_SELECTOR).count()
            if count >= target:
                return True
            if count == last:
                stable += 1
                if stable >= stable_rounds:
                    return False
            else:
                stable = 0
            last = count
            page.evaluate(f"window.scrollBy(0, {random.randint(*step)})")
            page.wait_for_timeout(random.randint(*wait))
        return page.locator(ITEM_SELECTOR).count() >= target

    def close(self) -> None:
        for closer in (self._context.close, self._browser.close, self._pw.stop):
            try:
                closer()
            except Exception:
                pass
