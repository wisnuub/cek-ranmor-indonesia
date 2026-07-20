"""
Smart background plate crawler.
Menggunakan data suffix per kab/kota dari plate_patterns.py.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from database import AsyncSessionLocal
from crud import save_vehicle, get_or_create_crawler_job, update_crawler_job
from adapters import ADAPTERS
from plate_patterns import (
    generate_smart_suffixes, get_number_range,
    guess_jenis, get_kabkota_from_suffix, REGION_PREFIX,
)

log = logging.getLogger("crawler")

CRAWLABLE_REGIONS = {"jabar", "jateng", "diy", "bali"}  # No NIK needed

_tasks:      dict[str, asyncio.Task] = {}
_stop_flags: dict[str, bool]         = {}
_progress:   dict[str, dict]         = {}


async def _run(region: str, delay: float, mode: str):
    adapter = ADAPTERS.get(region)
    prefix  = REGION_PREFIX.get(region)
    if not adapter or not prefix:
        log.error(f"[{region}] No adapter/prefix"); return

    num_lo, num_hi = get_number_range(region, mode)
    suffixes = generate_smart_suffixes(region)

    async with AsyncSessionLocal() as db:
        job = await get_or_create_crawler_job(db, region)
        # Resume: skip suffixes & numbers already tried
        resume_suffix = None
        resume_num    = 0
        if job.last_plate:
            lp = job.last_plate.removeprefix(prefix)
            num_str = "".join(c for c in lp if c.isdigit())
            suf_str = "".join(c for c in lp if c.isalpha())
            resume_suffix = suf_str or None
            resume_num    = int(num_str) if num_str else 0
        await update_crawler_job(db, region, status="running", started_at=datetime.utcnow())

    log.info(f"[{region}] START prefix={prefix} mode={mode} "
             f"numbers={num_lo}-{num_hi} suffixes={len(suffixes):,}")

    tried = 0; found = 0
    _progress[region] = {"tried": 0, "found": 0, "last": "", "status": "running"}

    past_resume = (resume_suffix is None)

    for suffix in suffixes:
        if not past_resume:
            if suffix == resume_suffix:
                past_resume = True
            else:
                continue

        kab = get_kabkota_from_suffix(region, suffix)

        for num in range(num_lo, num_hi + 1):
            # Skip numbers already tried on resume suffix
            if not past_resume or (suffix == resume_suffix and num <= resume_num):
                continue

            if _stop_flags.get(region):
                plate = f"{prefix}{num}{suffix}"
                await _checkpoint(region, plate, tried, found, "paused")
                log.info(f"[{region}] Paused at {plate}")
                return

            plate = f"{prefix}{num}{suffix}"
            inc   = await _try(adapter, plate, region, kab)
            tried += 1; found += inc

            if tried % 500 == 0:
                await _checkpoint(region, plate, tried, found, "running")
                pct = (tried / (len(suffixes) * (num_hi - num_lo + 1))) * 100
                log.info(f"[{region}] tried={tried:,} found={found} last={plate} ({pct:.2f}%)")

            _progress[region] = {"tried": tried, "found": found,
                                  "last": plate, "kab": kab, "status": "running"}
            await asyncio.sleep(delay)

    await _checkpoint(region, "", tried, found, "done")
    log.info(f"[{region}] DONE tried={tried:,} found={found}")


async def _try(adapter, plate: str, region: str, kab: str) -> int:
    try:
        info = await adapter.fetch(plate)
        if info.merk or info.model:
            # Inject kabkota info if adapter didn't fill it
            if not info.region_name:
                info.region_name = kab
            async with AsyncSessionLocal() as db:
                await save_vehicle(db, info)
            log.info(f"  ✓ {plate} → {info.merk} {info.model} ({kab})")
            return 1
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.debug(f"  ✗ {plate}: {e}")
    return 0


async def _checkpoint(region, plate, tried, found, status):
    async with AsyncSessionLocal() as db:
        await update_crawler_job(db, region, last_plate=plate,
                                 total_tried=tried, total_found=found, status=status)
    _progress[region] = {"tried": tried, "found": found, "last": plate, "status": status}


# ── Public API ────────────────────────────────────────────────────────────

def start_crawler(region: str, delay: float = 1.5, mode: str = "all") -> dict:
    if region not in CRAWLABLE_REGIONS:
        return {"error": f"Region '{region}' butuh NIK atau belum didukung. Crawlable: {list(CRAWLABLE_REGIONS)}"}
    if region not in ADAPTERS:
        return {"error": f"Tidak ada adapter untuk '{region}'"}
    if region in _tasks and not _tasks[region].done():
        return {"status": "already_running", **_progress.get(region, {})}

    _stop_flags[region] = False
    _tasks[region] = asyncio.create_task(_run(region, delay, mode))

    prefix = REGION_PREFIX.get(region, "?")
    lo, hi = get_number_range(region, mode)
    return {
        "status":  "started",
        "region":  region,
        "prefix":  prefix,
        "mode":    mode,
        "delay_s": delay,
        "number_range": f"{lo}–{hi}",
        "note": "Phase 1: known suffixes per kab/kota → Phase 2: brute-force",
    }


def stop_crawler(region: str) -> dict:
    _stop_flags[region] = True
    return {"status": "stopping", "region": region}


def crawler_status() -> dict:
    return {
        region: {
            "running":  not task.done(),
            "stopping": _stop_flags.get(region, False),
            **_progress.get(region, {}),
        }
        for region, task in _tasks.items()
    }


def add_known_suffix(region: str, suffix: str) -> dict:
    """Tambah suffix yang diketahui valid secara runtime."""
    from plate_patterns import KABKOTA_MAP
    suffix = suffix.upper()
    if not suffix:
        return {"error": "Suffix kosong"}
    fl = suffix[0]
    if region not in KABKOTA_MAP:
        KABKOTA_MAP[region] = {}
    if fl not in KABKOTA_MAP[region]:
        KABKOTA_MAP[region][fl] = f"Unknown ({suffix})"
    return {"added": suffix, "first_letter": fl, "region": region}
