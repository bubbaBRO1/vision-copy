from playwright.async_api import async_playwright
from .base_scraper import BaseScraper, ScraperResult, CaptchaDetected


class YandexScraper(BaseScraper):
    name = "Yandex Images"
    timeout_ms = 20000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            try:
                page = await context.new_page()
                await page.goto("https://yandex.com/images/", timeout=self.timeout_ms)

                # Click camera icon
                btn = await page.query_selector("button.input__btn[aria-label*='image'], .cbir-button, [class*='camera']")
                if btn:
                    await btn.click()
                else:
                    await page.goto("https://yandex.com/images/search?rpt=imageview&url=&cbir_id=&cbir_page=sites", timeout=self.timeout_ms)

                file_input = await page.wait_for_selector("input[type=file]", timeout=5000)
                await file_input.set_input_files(image_path)
                await page.wait_for_url("**/search?**", timeout=self.timeout_ms)
                await page.wait_for_load_state("networkidle", timeout=8000)

                content = await page.content()
                if self._detect_captcha(content):
                    raise CaptchaDetected()

                results = []
                items = await page.query_selector_all(".serp-item, .cbir-section__page-link")
                for item in items[:15]:
                    try:
                        a = await item.query_selector("a")
                        img = await item.query_selector("img")
                        url = await a.get_attribute("href") if a else None
                        thumb = await img.get_attribute("src") if img else None
                        title_el = await item.query_selector(".organic__title, .serp-item__title")
                        title = await title_el.inner_text() if title_el else None
                        if not url:
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
