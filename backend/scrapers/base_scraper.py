"""Base scraper: Playwright stealth, rotating UA, retry, health check, normalized output."""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0",
]


@dataclass
class ScraperResult:
    url: str
    thumbnail: Optional[str] = None
    title: Optional[str] = None
    similarity_pct: Optional[float] = None
    source_domain: Optional[str] = None
    engine: str = ""
    found_at: Optional[str] = None
    page_context: Optional[str] = None


class BaseScraper(ABC):
    name: str = "base"
    timeout_ms: int = 15000
    max_retries: int = 3

    def __init__(self):
        self._consecutive_failures = 0
        self._disabled_until = 0.0

    def _is_healthy(self) -> bool:
        if self._consecutive_failures >= 5 and time.time() < self._disabled_until:
            return False
        if time.time() >= self._disabled_until:
            self._disabled_until = 0.0
        return True

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= 5:
            self._disabled_until = time.time() + 600  # re-enable after 10min

    def _record_success(self):
        self._consecutive_failures = 0
        self._disabled_until = 0.0

    @abstractmethod
    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        ...

    async def search(self, image_path: str) -> list[ScraperResult]:
        if not self._is_healthy():
            return [ScraperResult(url="", engine=self.name, page_context="Engine temporarily unavailable")]

        for attempt in range(self.max_retries):
            try:
                results = await self._do_search(image_path)
                self._record_success()
                for r in results:
                    r.engine = self.name
                return results
            except CaptchaDetected:
                self._record_failure()
                return [ScraperResult(url="", engine=self.name, page_context="CAPTCHA detected")]
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    self._record_failure()
                    return [ScraperResult(url="", engine=self.name, page_context=f"Error: {e}")]
        return []

    async def _get_browser_context(self, playwright):
        browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        ua = random.choice(USER_AGENTS)
        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
        """)
        return browser, context

    def _detect_captcha(self, content: str) -> bool:
        captcha_signals = ["captcha", "robot", "unusual traffic", "verify you are human", "i'm not a robot"]
        lower = content.lower()
        return any(s in lower for s in captcha_signals)

    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.replace("www.", "")
        except Exception:
            return ""


class CaptchaDetected(Exception):
    pass
