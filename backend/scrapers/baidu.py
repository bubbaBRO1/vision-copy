from playwright.async_api import async_playwright
from .base_scraper import BaseScraper, ScraperResult, CaptchaDetected


class BaiduScraper(BaseScraper):
    name = "Baidu Images"
    timeout_ms = 25000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            try:
                page = await context.new_page()
                await page.goto("https://image.baidu.com/", timeout=self.timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=8000)

                # Click camera icon
                cam = await page.query_selector(".camera-icon, #sttb, [class*='camera']")
                if cam:
                    await cam.click()
                    await page.wait_for_timeout(1000)

                fi = await page.query_selector("input[type=file]")
                if fi:
                    await fi.set_input_files(image_path)
                    await page.wait_for_load_state("networkidle", timeout=self.timeout_ms)

                content = await page.content()
                if self._detect_captcha(content):
                    raise CaptchaDetected()

                results = []
                items = await page.query_selector_all(".imgitem, .result-op, .img-item")
                for item in items[:15]:
                    try:
                        a = await item.query_selector("a")
                        img = await item.query_selector("img")
                        url = await a.get_attribute("href") if a else None
                        thumb = await img.get_attribute("src") if img else None
                        if not url:
                            continue
                        results.append(ScraperResult(
                            url=url,
                            thumbnail=thumb,
                            source_domain=self._extract_domain(url),
                            found_at=page.url,
                        ))
                    except Exception:
                        continue
                return results
            finally:
                await context.close()
                await browser.close()
