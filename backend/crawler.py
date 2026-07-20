"""
Background plate enumerator / crawler.
Only works on regions that don't require NIK:
  Jawa Barat (D,F,Z,E,T), Jawa Tengah (H,G,K,R,AA,AD), DIY (AB), Bali (DK)
"""
import asyncio
import itertools
import logging
import string
from datetime import datetime
from typing import Optional

from database import AsyncSessionLocal
from crud import save_vehicle, get_or_create_crawler_job, update_crawler_job
from adapters import ADAPTERS
from router import PLATE_TO_REGION

log = logging.getLogger("crawler")

# Regions that don't require NIK — safe to crawl
CRAWLABLE_PREFIXES: dict[str, str] = {
    prefix: region
    for prefix, region in PLATE_TO_REGION.items()
    if region in {"jabar", "jateng", "diy", "bali"}
}

# One active crawler task per region
_active_tasks: dict[str, asyncio.Task] = {}
_stop_flags:   dict[str, bool] = {}

# Letters used in Indonesian plates (skip I and O to avoid confusion)
PLATE_LETTERS = [c for c in string.ascii_uppercase if c not in ("I", "O")]


def generate_plates(prefix: str, resume_after: Optional[str] = None):
    """
    Yield plate strings for a given prefix.
    Order: PREFIX NUM SUFFIX
      NUM    : 1 → 9999
      SUFFIX : A, B, ... Z, AA, AB, ... ZZ, AAA, ... ZZZ
    Supports resume via resume_after (skip plates up to and including that plate).
    """
    found_resume = (resume_after is None)

    for length in (1, 2, 3):
        for combo in itertools.product(PLATE_LETTERS, repeat=length):
            suffix = "".join(combo)
            for num in range(1, 10000):
                plate = f"{prefix}{num}{suffix}"
                if not found_resume:
                    if plate == resume_after:
                        found_resume = True
                    continue
                yield plate


async def _crawl_region(region: str, prefix: str, delay: float = 1.5):
    """
    Core crawler loop for one region/prefix.
    delay = seconds between requests (be polite to Samsat servers).
    """
    adapter = ADAPTERS.get(region)
    if not adapter:
        log.warning(f"No adapter for {region}, skipping")
        return

    async with AsyncSessionLocal() as db:
        job = await get_or_create_crawler_job(db, region)
        resume = job.last_plate
        await update_crawler_job(db, region, status="running", started_at=datetime.utcnow())

    log.info(f"[crawler:{region}] Starting (prefix={prefix}, resume={resume})")

    tried = 0
    found = 0

    for plate in generate_plates(prefix, resume_after=resume):
        if _stop_flags.get(region):
            log.info(f"[crawler:{region}] Stopped at {plate}")
            async with AsyncSessionLocal() as db:
                await update_crawler_job(db, region, status="paused", last_plate=plate,
                                         total_tried=tried, total_found=found)
            return

        try:
            info = await adapter.fetch(plate)
            tried += 1

            if info.merk or info.model:
                found += 1
                log.info(f"[crawler:{region}] FOUND {plate} → {info.merk} {info.model}")
                async with AsyncSessionLocal() as db:
                    await save_vehicle(db, info)

            # Checkpoint every 100 plates
            if tried % 100 == 0:
                async with AsyncSessionLocal() as db:
                    await update_crawler_job(db, region, last_plate=plate,
                                             total_tried=tried, total_found=found)
                log.info(f"[crawler:{region}] Progress: tried={tried}, found={found}, last={plate}")

            await asyncio.sleep(delay)

        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"[crawler:{region}] Error on {plate}: {e}")
            await asyncio.sleep(delay * 2)

    async with AsyncSessionLocal() as db:
        await update_crawler_job(db, region, status="done",
                                 total_tried=tried, total_found=found)
    log.info(f"[crawler:{region}] DONE. tried={tried}, found={found}")


def start_crawler(region: str, delay: float = 1.5) -> dict:
    """Start background crawler for a region. Returns status."""
    if region not in {r for r in ADAPTERS}:
        return {"error": f"No adapter for region '{region}'"}

    # Find crawlable prefix for this region
    prefixes = [p for p, r in CRAWLABLE_PREFIXES.items() if r == region]
    if not prefixes:
        return {"error": f"Region '{region}' requires NIK — cannot auto-crawl"}

    if region in _active_tasks and not _active_tasks[region].done():
        return {"status": "already_running", "region": region}

    prefix = prefixes[0]  # Use primary prefix
    _stop_flags[region] = False

    task = asyncio.create_task(_crawl_region(region, prefix, delay))
    _active_tasks[region] = task
    return {"status": "started", "region": region, "prefix": prefix, "delay": delay}


def stop_crawler(region: str) -> dict:
    _stop_flags[region] = True
    return {"status": "stopping", "region": region}


def crawler_status() -> dict:
    return {
        region: {
            "running": not task.done(),
            "stop_requested": _stop_flags.get(region, False),
        }
        for region, task in _active_tasks.items()
    }
