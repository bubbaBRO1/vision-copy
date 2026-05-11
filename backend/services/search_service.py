"""Orchestrates imagetrace stages as async background job, emitting SSE events via Redis pub/sub."""
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import AsyncSessionLocal
from models.search import Search, SearchStatus
from services.rate_limiter import get_redis

settings = get_settings()
UTC = timezone.utc

STAGE_PIPELINE = [
    ("stage0_hashing", "analyze", "Hashing & NSFW"),
    ("stage1_metadata", "analyze", "EXIF & Metadata"),
    ("stage2_forensics", "analyze", "Forensics (ELA)"),
    ("stage3_steganography", "analyze", "Steganography"),
    ("stage4_content", "analyze", "Face & Object Detection"),
    ("stage12_ai_analysis", "analyze", "AI Analysis (CLIP/DeepFace)"),
    ("stage5_geolocation", "analyze", "Geolocation"),
    ("stage6_reverse_search", "analyze", "Reverse Image Search"),
    ("stage7_face_search", "analyze", "Face Search (PimEyes/FaceCheck)"),
    ("stage8_report", "analyze", "Scoring & Report"),
]

# Stages run conditionally based on stage4 content extraction output
CONDITIONAL_STAGES = [
    # (module, fn, label, required_key_in_stage4_results)
    ("stage9_social", "analyze", "Social & Username Search", "emails"),
    ("stage10_webscrape", "analyze", "Web Intelligence", "urls"),
    ("stage11_domain_intel", "analyze", "Domain Intelligence", "domains"),
    ("stage15_leaks", "analyze", "Leaked Credentials", "emails"),
    ("stage14_blockchain", "analyze", "Blockchain Detection", "text"),
    ("stage13_archive", "analyze", "Web Archiving", "urls"),
    ("stage17_recognition", "analyze", "Vehicle & Brand Recognition", None),
]


async def publish_event(search_id: str, stage: str, status: str, data: Any = None) -> None:
    r = get_redis()
    event = json.dumps({"stage": stage, "status": status, "data": data, "ts": time.time()})
    await r.publish(f"search:{search_id}", event)


async def save_results(db: AsyncSession, search_id: uuid.UUID, results: dict, error: str = None) -> None:
    search = await db.get(Search, search_id)
    if search:
        search.results_json = results
        search.status = SearchStatus.failed if error else SearchStatus.done
        search.error = error
        search.completed_at = datetime.now(UTC)
        if search.created_at:
            elapsed = (datetime.now(UTC) - search.created_at.replace(tzinfo=UTC)).total_seconds()
            search.duration_ms = int(elapsed * 1000)
        await db.commit()


async def run_analysis(search_id: uuid.UUID, image_path: str) -> None:
    """Entry point for background task. Owns its own DB session (request session is closed by then)."""
    async with AsyncSessionLocal() as db:
        search = await db.get(Search, search_id)
        if search:
            search.status = SearchStatus.running
            await db.commit()

        results: dict = {}
        error: str | None = None

        try:
            for module_name, fn_name, stage_label in STAGE_PIPELINE:
                await publish_event(str(search_id), stage_label, "running")
                t0 = time.time()
                try:
                    import importlib
                    mod = importlib.import_module(f"stages.{module_name}")
                    fn = getattr(mod, fn_name, None) or getattr(mod, "analyze", None) or getattr(mod, "run", None)
                    if fn is None:
                        raise AttributeError(f"No callable entry point in stages.{module_name}")
                    data = await asyncio.to_thread(fn, image_path)
                    elapsed_ms = int((time.time() - t0) * 1000)
                    results[stage_label] = data
                    await publish_event(str(search_id), stage_label, "done", {"elapsed_ms": elapsed_ms})
                except Exception as e:
                    elapsed_ms = int((time.time() - t0) * 1000)
                    results[stage_label] = {"error": str(e)}
                    await publish_event(str(search_id), stage_label, "failed", {"reason": str(e), "elapsed_ms": elapsed_ms})

            # Run Playwright scrapers concurrently
            await publish_event(str(search_id), "Web Scrapers", "running")
            try:
                scraper_results = await _run_scrapers(image_path)
                results["web_scrapers"] = scraper_results
                await publish_event(str(search_id), "Web Scrapers", "done", {"count": sum(len(v) for v in scraper_results.values())})
            except Exception as e:
                results["web_scrapers"] = {"error": str(e)}
                await publish_event(str(search_id), "Web Scrapers", "failed", {"reason": str(e)})

            # Conditional stages based on stage4 content
            stage4_data = results.get("Face & Object Detection", {})
            for module_name, fn_name, stage_label, required_key in CONDITIONAL_STAGES:
                if required_key and not stage4_data.get(required_key):
                    continue
                await publish_event(str(search_id), stage_label, "running")
                t0 = time.time()
                try:
                    import importlib
                    mod = importlib.import_module(f"stages.{module_name}")
                    fn = getattr(mod, fn_name, None) or getattr(mod, "analyze", None) or getattr(mod, "run", None)
                    if fn is None:
                        raise AttributeError(f"No callable entry point in stages.{module_name}")
                    data = await asyncio.to_thread(fn, image_path)
                    elapsed_ms = int((time.time() - t0) * 1000)
                    results[stage_label] = data
                    await publish_event(str(search_id), stage_label, "done", {"elapsed_ms": elapsed_ms})
                except ModuleNotFoundError:
                    pass  # stage not yet implemented, skip silently
                except Exception as e:
                    elapsed_ms = int((time.time() - t0) * 1000)
                    results[stage_label] = {"error": str(e)}
                    await publish_event(str(search_id), stage_label, "failed", {"reason": str(e), "elapsed_ms": elapsed_ms})

            # Vision LLM analysis
            await publish_event(str(search_id), "Vision AI", "running")
            try:
                from ai.vision_analyzer import analyze_image
                vision_data = await asyncio.to_thread(analyze_image, image_path)
                results["Vision AI"] = vision_data
                await publish_event(str(search_id), "Vision AI", "done")
            except Exception as e:
                results["Vision AI"] = {"error": str(e)}
                await publish_event(str(search_id), "Vision AI", "failed", {"reason": str(e)})

            # Auto dossier generation
            await publish_event(str(search_id), "AI Dossier", "running")
            try:
                from ai.dossier import generate_dossier
                search_obj = await db.get(Search, search_id)
                filename = search_obj.filename if search_obj else "image"
                dossier_data = await asyncio.to_thread(generate_dossier, results, filename)
                results["AI Dossier"] = dossier_data
                await publish_event(str(search_id), "AI Dossier", "done")
            except Exception as e:
                results["AI Dossier"] = {"error": str(e)}
                await publish_event(str(search_id), "AI Dossier", "failed", {"reason": str(e)})

        except Exception as e:
            error = str(e)

        await save_results(db, search_id, results, error)
        await publish_event(str(search_id), "__done__", "done", {"search_id": str(search_id)})


async def _run_scrapers(image_path: str) -> dict:
    """Run all Playwright scrapers concurrently."""
    from scrapers.google_lens import GoogleLensScraper
    from scrapers.yandex import YandexScraper
    from scrapers.tineye import TinEyeScraper
    from scrapers.saucenao import SauceNAOScraper
    from scrapers.iqdb import IQDBScraper
    from scrapers.bing_visual import BingVisualScraper

    scrapers = [
        GoogleLensScraper(),
        YandexScraper(),
        TinEyeScraper(),
        SauceNAOScraper(),
        IQDBScraper(),
        BingVisualScraper(),
    ]

    async def _run_one(scraper):
        try:
            return scraper.__class__.__name__, await scraper.search(image_path)
        except Exception as e:
            return scraper.__class__.__name__, [{"error": str(e)}]

    tasks = [_run_one(s) for s in scrapers]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    return {name: data for item in results_list if isinstance(item, tuple) for name, data in [item]}


async def stream_search_events(search_id: str):
    """Async generator: yields SSE-formatted strings from Redis pub/sub."""
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"search:{search_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
                event = json.loads(data)
                if event.get("stage") == "__done__":
                    break
    finally:
        await pubsub.unsubscribe(f"search:{search_id}")
        await pubsub.aclose()
