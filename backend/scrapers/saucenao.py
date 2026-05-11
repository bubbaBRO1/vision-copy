import httpx
from pathlib import Path
from .base_scraper import BaseScraper, ScraperResult


class SauceNAOScraper(BaseScraper):
    name = "SauceNAO"
    timeout_ms = 15000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            with open(image_path, "rb") as f:
                r = await client.post(
                    "https://saucenao.com/search.php",
                    data={"output_type": 2, "numres": 16},
                    files={"file": (Path(image_path).name, f, "image/jpeg")},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; VISION-OSINT/1.0)"},
                )
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for result in data.get("results", [])[:15]:
                header = result.get("header", {})
                data_block = result.get("data", {})
                similarity = float(header.get("similarity", 0))
                ext_urls = data_block.get("ext_urls", [])
                url = ext_urls[0] if ext_urls else ""
                title = data_block.get("title") or data_block.get("source") or header.get("index_name", "")
                thumb = header.get("thumbnail", "")
                results.append(ScraperResult(
                    url=url,
                    thumbnail=thumb,
                    title=title,
                    similarity_pct=similarity,
                    source_domain=self._extract_domain(url) if url else "",
                    found_at="https://saucenao.com",
                ))
            return [r for r in results if r.url]
