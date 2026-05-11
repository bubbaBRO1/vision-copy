import httpx
from pathlib import Path
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, ScraperResult


class IQDBScraper(BaseScraper):
    name = "IQDB"
    timeout_ms = 12000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            with open(image_path, "rb") as f:
                r = await client.post(
                    "https://iqdb.org/",
                    files={"file": (Path(image_path).name, f, "image/jpeg")},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"},
                )
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for table in soup.select("#pages > div"):
                try:
                    a = table.select_one("a[href]")
                    img = table.select_one("img")
                    similarity_td = table.select_one("td.similarity")
                    url = a["href"] if a else ""
                    if url.startswith("//"):
                        url = "https:" + url
                    thumb = img["src"] if img else None
                    if thumb and thumb.startswith("//"):
                        thumb = "https:" + thumb
                    sim_text = similarity_td.get_text() if similarity_td else "0%"
                    try:
                        sim = float(sim_text.replace("%", "").strip())
                    except Exception:
                        sim = None
                    if not url or "iqdb.org" in url:
                        continue
                    results.append(ScraperResult(
                        url=url,
                        thumbnail=thumb,
                        similarity_pct=sim,
                        source_domain=self._extract_domain(url),
                        found_at="https://iqdb.org",
                    ))
                except Exception:
                    continue
            return results[:10]
