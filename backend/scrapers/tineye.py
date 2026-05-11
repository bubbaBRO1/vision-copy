import httpx
from pathlib import Path
from .base_scraper import BaseScraper, ScraperResult, CaptchaDetected
from config import get_settings

settings = get_settings()


class TinEyeScraper(BaseScraper):
    name = "TinEye"
    timeout_ms = 15000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        # Try official API first if key available
        if settings.tineye_api_key:
            return await self._api_search(image_path)
        return await self._scrape_search(image_path)

    async def _api_search(self, image_path: str) -> list[ScraperResult]:
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            with open(image_path, "rb") as f:
                r = await client.post(
                    "https://api.tineye.com/rest/search/",
                    data={"api_key": settings.tineye_api_key},
                    files={"image": f},
                )
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for match in data.get("results", {}).get("matches", [])[:15]:
                for img in match.get("image_urls", [])[:1]:
                    results.append(ScraperResult(
                        url=match.get("backlinks", [{}])[0].get("url", "") if match.get("backlinks") else img,
                        thumbnail=img,
                        title=match.get("domain"),
                        similarity_pct=match.get("score", 0) * 100,
                        source_domain=match.get("domain"),
                        found_at="https://tineye.com",
                    ))
            return results

    async def _scrape_search(self, image_path: str) -> list[ScraperResult]:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            try:
                page = await context.new_page()
                await page.goto("https://tineye.com/", timeout=self.timeout_ms)
                fi = await page.query_selector("input[type=file]")
                if fi:
                    await fi.set_input_files(image_path)
                    await page.wait_for_url("**/search/**", timeout=self.timeout_ms)
                    await page.wait_for_load_state("networkidle", timeout=8000)

                content = await page.content()
                if self._detect_captcha(content):
                    raise CaptchaDetected()

                results = []
                items = await page.query_selector_all(".match")
                for item in items[:15]:
                    try:
                        a = await item.query_selector("a.match-thumb")
                        img = await item.query_selector("img")
                        url = await a.get_attribute("href") if a else None
                        thumb = await img.get_attribute("src") if img else None
                        pct_el = await item.query_selector(".match-score")
                        pct_txt = await pct_el.inner_text() if pct_el else "0"
                        try:
                            pct = float(pct_txt.replace("%", "").strip())
                        except Exception:
                            pct = None
                        if not url:
                            continue
                        results.append(ScraperResult(
                            url=url,
                            thumbnail=thumb,
                            similarity_pct=pct,
                            source_domain=self._extract_domain(url),
                            found_at=page.url,
                        ))
                    except Exception:
                        continue
                return results
            finally:
                await context.close()
                await browser.close()
