import asyncio
import ipaddress
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from sqlalchemy import select

from config import get_settings
from database import AsyncSessionLocal
from models.search import BrowserAssistArtifact, BrowserAssistRun

UTC = timezone.utc
settings = get_settings()

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid"}


def normalize_result_url(url: str) -> str:
    parsed = urlparse(url)
    filtered_query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k not in TRACKING_PARAMS]
    path = parsed.path.rstrip("/") or "/"
    query = urlencode(filtered_query)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", query, ""))


def _hostname_is_private(hostname: str) -> bool:
    lowered = hostname.lower().strip()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(lowered)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        return False


def validate_browser_assist_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Browser Assist only supports http/https URLs")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    if _hostname_is_private(parsed.hostname):
        raise ValueError("Private or localhost targets are not allowed")
    return normalize_result_url(url)


async def append_run_log(run_id: uuid.UUID, message: str, **extra):
    async with AsyncSessionLocal() as db:
        run = await db.get(BrowserAssistRun, run_id)
        if not run:
            return
        logs = list(run.run_log or [])
        logs.append({
            "ts": datetime.now(UTC).isoformat(),
            "message": message,
            **extra,
        })
        run.run_log = logs
        run.updated_at = datetime.now(UTC)
        await db.commit()


async def run_browser_assist(run_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        run = await db.get(BrowserAssistRun, run_id)
        if not run:
            return
        run.status = "running"
        await db.commit()
        urls = list(run.approved_urls or [])
        user_id = run.user_id

    for url in urls:
        async with AsyncSessionLocal() as db:
            run = await db.get(BrowserAssistRun, run_id)
            if not run or run.status == "cancelled":
                return

        await append_run_log(run_id, "Navigating", url=url)
        artifact_payload = await _capture_artifact(url, run_id)

        async with AsyncSessionLocal() as db:
            run = await db.get(BrowserAssistRun, run_id)
            if not run:
                return

            visited = list(run.visited_urls or [])
            visited.append(artifact_payload["final_url"] or url)
            run.visited_urls = visited

            if run.persist_artifacts:
                db.add(
                    BrowserAssistArtifact(
                        run_id=run_id,
                        user_id=user_id,
                        source_url=url,
                        final_url=artifact_payload["final_url"],
                        title=artifact_payload["title"],
                        snippet=artifact_payload["snippet"],
                        screenshot_path=artifact_payload["screenshot_path"],
                        metadata_json=artifact_payload["metadata"],
                    )
                )

            await db.commit()

    async with AsyncSessionLocal() as db:
        run = await db.get(BrowserAssistRun, run_id)
        if run:
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            await db.commit()
    await append_run_log(run_id, "Run completed")


async def _capture_artifact(url: str, run_id: uuid.UUID) -> dict:
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return await _capture_artifact_fallback(url)

    artifact_dir = Path(settings.upload_dir) / "browser-assist" / str(run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = artifact_dir / f"{uuid.uuid4()}.png"

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=False)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.screenshot(path=str(screenshot_path), full_page=True)
            title = await page.title()
            final_url = page.url
            snippet = await page.locator("body").inner_text(timeout=3000)
            await context.close()
            await browser.close()
            return {
                "final_url": final_url,
                "title": title[:512] if title else None,
                "snippet": (snippet or "")[:500],
                "screenshot_path": str(screenshot_path),
                "metadata": {"capture": "playwright"},
            }
    except Exception:
        if screenshot_path.exists():
            screenshot_path.unlink(missing_ok=True)
        return await _capture_artifact_fallback(url)


async def _capture_artifact_fallback(url: str) -> dict:
    try:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
            text = response.text or ""
            title = None
            if "<title" in text.lower():
                lower = text.lower()
                start = lower.find("<title")
                start = text.find(">", start) + 1
                end = lower.find("</title>", start)
                title = text[start:end].strip()[:512]
            snippet = " ".join(text.split())[:500]
            return {
                "final_url": str(response.url),
                "title": title,
                "snippet": snippet,
                "screenshot_path": None,
                "metadata": {"capture": "httpx-fallback", "status_code": response.status_code},
            }
    except Exception as exc:
        return {
            "final_url": url,
            "title": None,
            "snippet": "",
            "screenshot_path": None,
            "metadata": {"capture": "failed", "error": str(exc)},
        }


async def stream_browser_assist(run_id: uuid.UUID):
    last_count = 0
    while True:
        async with AsyncSessionLocal() as db:
            run = await db.get(BrowserAssistRun, run_id)
            if not run:
                yield 'data: {"error":"run_not_found"}\n\n'
                return
            logs = list(run.run_log or [])
            for item in logs[last_count:]:
                yield f"data: {__import__('json').dumps(item)}\n\n"
            last_count = len(logs)
            if run.status in {"completed", "failed", "cancelled"}:
                yield 'data: {"stage":"__done__","status":"done"}\n\n'
                return
        await asyncio.sleep(0.5)
