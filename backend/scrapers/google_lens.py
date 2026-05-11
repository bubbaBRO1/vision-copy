import base64
from pathlib import Path
from playwright.async_api import async_playwright
from .base_scraper import BaseScraper, ScraperResult, CaptchaDetected


class GoogleLensScraper(BaseScraper):
    name = "Google Lens"
    timeout_ms = 20000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            try:
                page = await context.new_page()
                await page.goto("https://lens.google.com/", timeout=self.timeout_ms)

                if self._detect_captcha(await page.content()):
                    raise CaptchaDetected()

                # Upload via file input
                await page.wait_for_selector("input[type=file]", timeout=5000)
                await page.set_input_files("input[type=file]", image_path)
                await page.wait_for_url("**/search?**", timeout=self.timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=10000)

                content = await page.content()
                if self._detect_captcha(content):
                    raise CaptchaDetected()

                results = []
                cards = await page.query_selector_all("div[data-item-index]")
                for card in cards[:15]:
                    try:
                        a = await card.query_selector("a[href]")
                        img = await card.query_selector("img")
                        title_el = await card.query_selector("span, h3")
                        url = await a.get_attribute("href") if a else None
                        thumb = await img.get_attribute("src") if img else None
                        title = await title_el.inner_text() if title_el else None
                        if url and not url.startswith("http"):
                            continue
                        results.append(ScraperResult(
                            url=url or "",
                            thumbnail=thumb,
                            title=title,
                            source_domain=self._extract_domain(url or ""),
                            found_at=page.url,
                        ))
                    except Exception:
                        continue
                return results
            finally:
                await context.close()
                await browser.close()
