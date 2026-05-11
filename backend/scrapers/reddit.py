import hashlib
import httpx
from .base_scraper import BaseScraper, ScraperResult


class RedditScraper(BaseScraper):
    name = "Reddit"
    timeout_ms = 10000

    async def _do_search(self, image_path: str) -> list[ScraperResult]:
        # Compute hash → search Reddit for image hash mentions
        with open(image_path, "rb") as f:
            img_hash = hashlib.md5(f.read()).hexdigest()

        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            r = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": img_hash, "type": "link", "limit": 10},
                headers={"User-Agent": "VISION-OSINT/1.0"},
            )
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for post in data.get("data", {}).get("children", []):
                pd = post.get("data", {})
                url = pd.get("url", "")
                thumb = pd.get("thumbnail", "")
                if thumb in ("self", "default", "nsfw", ""):
                    thumb = None
                results.append(ScraperResult(
                    url=f"https://reddit.com{pd.get('permalink', '')}",
                    thumbnail=thumb,
                    title=pd.get("title"),
                    source_domain="reddit.com",
                    found_at="https://www.reddit.com/search",
                    page_context=f"r/{pd.get('subreddit', '')} — {pd.get('score', 0)} pts",
                ))
            return results
