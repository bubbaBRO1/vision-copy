"""Multi-source deep research pipeline. All free APIs."""
import asyncio
import json
from typing import AsyncGenerator, Optional
import httpx
from .ollama_client import stream_chat, generate_one_shot, RESEARCH_MODEL
from .prompts import research_synthesis_prompt, query_expansion_prompt

DEPTH_SOURCES = {
    "quick": 2,     # queries
    "standard": 5,
    "deep": 10,
}
DEPTH_URLS = {
    "quick": 5,
    "standard": 15,
    "deep": 30,
}


async def expand_queries(topic: str, n: int = 5) -> list[str]:
    prompt = query_expansion_prompt(topic, n)
    result = await generate_one_shot(prompt, model=RESEARCH_MODEL)
    try:
        start = result.find("[")
        end = result.rfind("]") + 1
        return json.loads(result[start:end])[:n]
    except Exception:
        return [topic]


async def _ddg_search(query: str, max_results: int = 20) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for a in soup.select("a.result__a")[:max_results]:
                href = a.get("href", "")
                if href and href.startswith("http"):
                    results.append({"url": href, "title": a.get_text(strip=True)})
            return results
    except Exception:
        return []


async def _wikipedia_search(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={"action": "search", "list": "search", "srsearch": query, "format": "json", "srlimit": 3},
            )
            results = []
            for item in r.json().get("query", {}).get("search", []):
                results.append({
                    "url": f"https://en.wikipedia.org/wiki/{item['title'].replace(' ', '_')}",
                    "title": item["title"],
                    "snippet": item.get("snippet", ""),
                })
            return results
    except Exception:
        return []


async def _arxiv_search(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": f"all:{query}", "max_results": 3},
            )
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            results = []
            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", namespaces=ns, default="").strip()
                link_el = entry.find("atom:link[@rel='alternate']", ns)
                url = link_el.get("href") if link_el is not None else ""
                summary = entry.findtext("atom:summary", namespaces=ns, default="")[:500]
                results.append({"url": url, "title": title, "snippet": summary})
            return results
    except Exception:
        return []


async def _hackernews_search(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "hitsPerPage": 5},
            )
            return [
                {
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "title": hit.get("title", ""),
                    "snippet": hit.get("story_text", "")[:300],
                }
                for hit in r.json().get("hits", [])
                if hit.get("url") or hit.get("objectID")
            ]
    except Exception:
        return []


async def _reddit_search(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "limit": 5, "type": "link"},
                headers={"User-Agent": "VISION-OSINT/1.0"},
            )
            return [
                {
                    "url": f"https://reddit.com{child['data']['permalink']}",
                    "title": child["data"]["title"],
                    "snippet": child["data"].get("selftext", "")[:300],
                }
                for child in r.json().get("data", {}).get("children", [])
            ]
    except Exception:
        return []


async def extract_content(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            from readabilipy import simple_json_from_html_string
            result = simple_json_from_html_string(r.text, use_readability=True)
            text = result.get("plain_text", "") or ""
            return text[:3000] if text else None
    except Exception:
        return None


async def run_research(job_id: str, query: str, depth: str = "standard") -> AsyncGenerator[str, None]:
    """Yields markdown tokens for SSE streaming."""
    n_queries = DEPTH_SOURCES.get(depth, 5)
    max_urls = DEPTH_URLS.get(depth, 15)

    yield "**VISION Deep Research**\n\n"
    yield f"**Topic:** {query}\n"
    yield f"**Depth:** {depth.title()}\n\n"
    yield "---\n\n"

    # Stage 1: expand queries
    yield "🔍 **Expanding search queries...**\n\n"
    queries = await expand_queries(query, n_queries)
    for q in queries:
        yield f"- `{q}`\n"
    yield "\n"

    # Stage 2: parallel source scraping
    yield "📡 **Scraping sources...**\n\n"
    tasks = []
    for q in queries[:3]:
        tasks.extend([
            _ddg_search(q, 10),
            _wikipedia_search(q),
            _arxiv_search(q),
            _hackernews_search(q),
            _reddit_search(q),
        ])
    all_source_lists = await asyncio.gather(*tasks, return_exceptions=True)
    all_sources: list[dict] = []
    for src_list in all_source_lists:
        if isinstance(src_list, list):
            all_sources.extend(src_list)

    # Deduplicate by URL
    seen = set()
    unique_sources = []
    for s in all_sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique_sources.append(s)

    yield f"Found **{len(unique_sources)}** unique sources\n\n"

    # Stage 3: extract content from top URLs
    yield "📖 **Extracting content...**\n\n"
    extract_tasks = [extract_content(s["url"]) for s in unique_sources[:max_urls]]
    extracted = await asyncio.gather(*extract_tasks, return_exceptions=True)

    source_chunks = []
    for i, (source, content) in enumerate(zip(unique_sources[:max_urls], extracted)):
        if isinstance(content, str) and content.strip():
            source_chunks.append(f"[{i+1}] {source['title']}\nURL: {source['url']}\n{content[:1500]}")

    yield f"Extracted content from **{len(source_chunks)}** pages\n\n"
    yield "---\n\n"
    yield "## 📊 Research Report\n\n"

    # Stage 4: AI synthesis
    sources_text = "\n\n---\n\n".join(source_chunks[:15])
    synthesis_msg = research_synthesis_prompt(query, sources_text)

    async for token in stream_chat(
        [{"role": "user", "content": synthesis_msg}],
        model=RESEARCH_MODEL,
    ):
        yield token

    yield "\n\n---\n\n*Report generated by VISION Deep Research Engine*\n"
