"""Background cleanup: delete uploaded files older than RETENTION_DAYS (default 7)."""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import get_settings
from database import AsyncSessionLocal
from models.search import Search, SearchStatus

settings = get_settings()
UTC = timezone.utc
RETENTION_DAYS = int(os.environ.get("FILE_RETENTION_DAYS", "7"))


async def cleanup_old_files() -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    deleted_files = 0
    deleted_records = 0
    errors = []

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(Search).where(Search.created_at < cutoff, Search.status == SearchStatus.done)
        )
        old_searches = result.scalars().all()

        for search in old_searches:
            if search.file_path:
                path = Path(search.file_path)
                # Safety: only delete files within the upload dir
                upload_dir = Path(settings.upload_dir).resolve()
                try:
                    resolved = path.resolve()
                    if resolved.is_relative_to(upload_dir) and resolved.exists():
                        resolved.unlink()
                        deleted_files += 1
                        # Also clean sidecar files
                        for suffix in (".ocr.txt", ".hashes.txt", ".plates.txt"):
                            sidecar = Path(str(resolved) + suffix)
                            if sidecar.exists():
                                sidecar.unlink()
                except Exception as e:
                    errors.append(str(e))

            search.file_path = None
            deleted_records += 1

        await db.commit()

    return {
        "deleted_files": deleted_files,
        "cleaned_records": deleted_records,
        "errors": errors,
        "retention_days": RETENTION_DAYS,
        "cutoff": cutoff.isoformat(),
    }


async def run_cleanup_loop():
    """Run cleanup every 24 hours."""
    while True:
        await asyncio.sleep(86400)
        try:
            result = await cleanup_old_files()
            print(f"[cleanup] Deleted {result['deleted_files']} files, {result['cleaned_records']} records")
        except Exception as e:
            print(f"[cleanup] Error: {e}")
