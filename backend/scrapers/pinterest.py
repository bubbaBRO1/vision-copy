from playwright.async_api import async_playwright
from .base_scraper import BaseScraper, ScraperResult, CaptchaDetected


class PinterestScraper(BaseScraper):
    name = "Pinterest"
    timeout_ms = 20000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            try:
                page = await context.new_page()
                await page.goto("https://www.pinterest.com/", timeout=self.timeout_ms)

                # Visual search via file upload API
                fi = await page.query_selector("input[type=file]")
                if not fi:
                    cam = await page.query_selector("[data-test-id='visual-search-button'], .camera-button")
                    if cam:
                        await cam.click()
                        fi = await page.wait_for_selector("input[type=file]", timeout=5000)

                if fi:
                    await fi.set_input_files(image_path)
                    await page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                content = await page.content()
                if self._detect_captcha(content):
                    raise CaptchaDetected()

                results = []
                pins = await page.query_selector_all("[data-test-id='pin'], .GrowthUnauthPin")
                for pin in pins[:15]:
                    try:
                        a = await pin.query_selector("a")
                        img = await pin.query_selector("img")
                        url = await a.get_attribute("href") if a else None
                        thumb = await img.get_attribute("src") if img else None
                        title = await img.get_attribute("alt") if img else None
                        if not url:
                            continue
                        full_url = f"https://pinterest.com{url}" if url.startswith("/") else url
                        results.append(ScraperResult(
                            url=full_url,
                            thumbnail=thumb,
                            title=title,
                            source_domain="pinterest.com",
                            found_at=page.url,
                        ))
                    except Exception:
                        continue
                return results
            finally:
                await context.close()
                await browser.close()
