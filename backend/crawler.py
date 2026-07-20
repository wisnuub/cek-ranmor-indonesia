"""
Smart background plate enumerator.
Strategi:
  1. Coba known suffixes dulu (dari plate_patterns.py) — jauh lebih cepat
  2. Lalu brute-force sisa kombinasi yang belum dicoba
  3. Rate-limited, resumable, per-region
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
from plate_patterns import (
    KNOWN_SUFFIXES, REGION_PRIMARY_PREFIX,
    get_search_order, guess_jenis_from_number,
    NUMBER_RANGES,
)

log = logging.getLogger("crawler")

# Regions yang bisa di-crawl (tidak butuh NIK)
CRAWLABLE_REGIONS = {"jabar", "jateng", "diy", "bali"}

# Letters untuk brute-force (tanpa I, O)
LETTERS = [c for c in string.ascii_uppercase if c not in ("I", "O")]

# Active tasks
_tasks:      dict[str, asyncio.Task] = {}
_stop_flags: dict[str, bool]         = {}
_progress:   dict[str, dict]         = {}


def _gen_suffixes_bruteforce(skip_known: list[str]):
    """Generate semua kombinasi suffix yang BELUM ada di known list."""
    known_set = set(skip_known)
    for length in (1, 2, 3):
        for combo in itertools.product(LETTERS, repeat=length):
            s = "".join(combo)
            if s not in known_set:
                yield s


def _gen_plates(prefix: str, suffixes: list[str], number_range: tuple[int, int]):
    """Yield plate strings: prefix + number + suffix, untuk range angka tertentu."""
    lo, hi = number_range
    for suffix in suffixes:
        for num in range(lo, hi + 1):
            yield f"{prefix}{num}{suffix}", suffix, num


async def _run(region: str, delay: float, mode: str):
    """
    Core crawler loop.
    mode: "all" | "motor" | "mobil"
    """
    adapter = ADAPTERS.get(region)
    prefix  = REGION_PRIMARY_PREFIX.get(region)
    if not adapter or not prefix:
        log.error(f"[{region}] No adapter/prefix")
        return

    known_suffixes, do_bruteforce = get_search_order(region)

    # Pilih range angka berdasarkan mode
    if mode == "motor":
        ranges = NUMBER_RANGES["motor"]
    elif mode == "mobil":
        ranges = NUMBER_RANGES["mobil"]
    else:
        ranges = NUMBER_RANGES["all"]

    async with AsyncSessionLocal() as db:
        job = await get_or_create_crawler_job(db, region)
        resume_suffix = None
        resume_num    = None
        if job.last_plate:
            # Parse last plate untuk resume: e.g. "DK5234FCR"
            p = job.last_plate.replace(prefix, "", 1)
            digits = ""
            letters_part = ""
            for i, ch in enumerate(p):
                if ch.isdigit():
                    digits += ch
                else:
                    letters_part = p[i:]
                    break
            resume_suffix = letters_part or None
            resume_num    = int(digits) if digits else None

        await update_crawler_job(db, region, status="running", started_at=datetime.utcnow())

    tried = 0
    found = 0
    _progress[region] = {"tried": 0, "found": 0, "last": "", "status": "running"}

    # Phase 1: known suffixes
    phase1_done = (resume_suffix is not None and resume_suffix not in known_suffixes)
    if not phase1_done:
        log.info(f"[{region}] Phase 1: {len(known_suffixes)} known suffixes")
        for num_range in ranges:
            for plate, suffix, num in _gen_plates(prefix, known_suffixes, num_range):
                # Resume check
                if resume_suffix and suffix == resume_suffix and resume_num and num <= resume_num:
                    continue

                if _stop_flags.get(region):
                    await _save_progress(region, plate, tried, found, "paused")
                    return

                found_inc = await _try_plate(adapter, plate, region)
                tried += 1
                found += found_inc

                _progress[region] = {"tried": tried, "found": found, "last": plate, "status": "running"}

                if tried % 200 == 0:
                    await _save_progress(region, plate, tried, found, "running")
                    log.info(f"[{region}] Phase1 tried={tried} found={found} last={plate}")

                await asyncio.sleep(delay)

    # Phase 2: brute-force remaining
    if do_bruteforce:
        log.info(f"[{region}] Phase 2: brute-force remaining suffixes")
        for suffix in _gen_suffixes_bruteforce(known_suffixes):
            if _stop_flags.get(region):
                break
            for num_range in ranges:
                for plate, _, num in _gen_plates(prefix, [suffix], num_range):
                    if _stop_flags.get(region):
                        await _save_progress(region, plate, tried, found, "paused")
                        return

                    found_inc = await _try_plate(adapter, plate, region)
                    tried += 1
                    found += found_inc

                    _progress[region] = {"tried": tried, "found": found, "last": plate, "status": "running"}

                    if tried % 500 == 0:
                        await _save_progress(region, plate, tried, found, "running")
                        log.info(f"[{region}] Phase2 tried={tried} found={found} last={plate}")

                    await asyncio.sleep(delay)

    await _save_progress(region, "", tried, found, "done")
    log.info(f"[{region}] DONE tried={tried} found={found}")


async def _try_plate(adapter, plate: str, region: str) -> int:
    """Try one plate. Returns 1 if found, 0 if not."""
    try:
        info = await adapter.fetch(plate)
        if info.merk or info.model:
            async with AsyncSessionLocal() as db:
                await save_vehicle(db, info)
            log.info(f"  FOUND {plate} → {info.merk} {info.model} {info.tahun}")
            return 1
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.debug(f"  ERR {plate}: {e}")
    return 0


async def _save_progress(region, plate, tried, found, status):
    async with AsyncSessionLocal() as db:
        await update_crawler_job(db, region,
            last_plate=plate, total_tried=tried,
            total_found=found, status=status)
    _progress[region] = {"tried": tried, "found": found, "last": plate, "status": status}


# ── Public API ────────────────────────────────────────────────────────────

def start_crawler(region: str, delay: float = 1.5, mode: str = "all") -> dict:
    if region not in CRAWLABLE_REGIONS:
        return {"error": f"Region '{region}' tidak bisa di-crawl (butuh NIK atau belum didukung)"}
    if region not in ADAPTERS:
        return {"error": f"Tidak ada adapter untuk region '{region}'"}
    if region in _tasks and not _tasks[region].done():
        return {"status": "already_running", "region": region, **_progress.get(region, {})}

    _stop_flags[region] = False
    task = asyncio.create_task(_run(region, delay, mode))
    _tasks[region] = task

    prefix = REGION_PRIMARY_PREFIX.get(region, "?")
    known  = len(KNOWN_SUFFIXES.get(region, []))
    return {
        "status":  "started",
        "region":  region,
        "prefix":  prefix,
        "mode":    mode,
        "delay_s": delay,
        "known_suffixes": known,
        "strategy": f"Phase 1: {known} known suffixes → Phase 2: brute-force sisanya",
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
    """Tambahkan suffix ke known list secara runtime (tanpa restart)."""
    suffix = suffix.upper().replace("I", "").replace("O", "")
    if region not in KNOWN_SUFFIXES:
        KNOWN_SUFFIXES[region] = []
    if suffix not in KNOWN_SUFFIXES[region]:
        KNOWN_SUFFIXES[region].append(suffix)
        return {"added": suffix, "total_known": len(KNOWN_SUFFIXES[region])}
    return {"already_exists": suffix}
