from playwright.async_api import async_playwright
from .base_scraper import BaseScraper, ScraperResult, CaptchaDetected


class BingVisualScraper(BaseScraper):
    name = "Bing Visual"
    timeout_ms = 20000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            try:
                page = await context.new_page()
                await page.goto("https://www.bing.com/visualsearch", timeout=self.timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=8000)

                fi = await page.query_selector("input[type=file]")
                if not fi:
                    # Try clicking upload button
                    btn = await page.query_selector("[aria-label*='Upload']")
                    if btn:
                        await btn.click()
                        fi = await page.wait_for_selector("input[type=file]", timeout=5000)

                if fi:
                    await fi.set_input_files(image_path)
                    await page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                content = await page.content()
                if self._detect_captcha(content):
                    raise CaptchaDetected()

                results = []
                cards = await page.query_selector_all(".richcard, .mc_vtvc, .vsd_card")
                for card in cards[:15]:
                    try:
                        a = await card.query_selector("a[href]")
                        img = await card.query_selector("img")
                        title_el = await card.query_selector("h3, .title, .rcs_btn_txt")
                        url = await a.get_attribute("href") if a else None
                        thumb = await img.get_attribute("src") if img else None
                        title = await title_el.inner_text() if title_el else None
                        if not url or url.startswith("#"):
                            continue
                        results.append(ScraperResult(
                            url=url,
                            thumbnail=thumb,
                            title=title,
                            source_domain=self._extract_domain(url),
                            found_at=page.url,
                        ))
                    except Exception:
                        continue
                return results
            finally:
                await context.close()
                await browser.close()
