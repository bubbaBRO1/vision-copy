import httpx
from pathlib import Path
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, ScraperResult


class ASCII2DScraper(BaseScraper):
    name = "ASCII2D"
    timeout_ms = 12000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000, follow_redirects=True) as client:
            with open(image_path, "rb") as f:
                r = await client.post(
                    "https://ascii2d.net/search/file",
                    files={"file": (Path(image_path).name, f, "image/jpeg")},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"},
                )
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for row in soup.select(".item-box")[:10]:
                try:
                    a = row.select_one(".detail-link a")
                    img = row.select_one("img")
                    title_el = row.select_one(".detail-link a")
                    url = a["href"] if a else ""
                    thumb = img["src"] if img else None
                    if thumb and thumb.startswith("/"):
                        thumb = "https://ascii2d.net" + thumb
                    title = title_el.get_text(strip=True) if title_el else None
                    if not url:
                        continue
                    results.append(ScraperResult(
                        url=url,
                        thumbnail=thumb,
                        title=title,
                        source_domain=self._extract_domain(url),
                        found_at="https://ascii2d.net",
                    ))
                except Exception:
                    continue
            return results
