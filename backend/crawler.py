"""
Smart background plate crawler dengan adaptive skip.

Strategi:
1. Suffix diurutkan: known per kab/kota dulu, baru brute-force
2. Untuk setiap suffix, coba angka dari range motor/mobil
3. Smart-skip: jika N angka berturut-turut kosong → lompat suffix berikutnya
   (dalam praktik, 1 seri suffix jarang melampaui 2000 nomor aktif)
"""
import asyncio
import logging
from datetime import datetime

from database import AsyncSessionLocal
from crud import save_vehicle, get_or_create_crawler_job, update_crawler_job
from adapters import ADAPTERS
from plate_patterns import (
    generate_smart_suffixes, get_number_range,
    get_kabkota_from_suffix, REGION_PREFIX,
)

log = logging.getLogger("crawler")

CRAWLABLE_REGIONS = {"jabar", "jateng", "diy", "bali"}

_tasks:      dict[str, asyncio.Task] = {}
_stop_flags: dict[str, bool]         = {}
_progress:   dict[str, dict]         = {}


async def _run(region: str, delay: float, mode: str,
               skip_after: int, specific_suffixes: list[str] | None):
    adapter = ADAPTERS.get(region)
    prefix  = REGION_PREFIX.get(region)
    if not adapter or not prefix:
        log.error(f"[{region}] No adapter/prefix"); return

    num_lo, num_hi = get_number_range(region, mode)

    # Suffix list: specific (user-provided) atau smart-generated
    if specific_suffixes:
        suffixes = [s.upper() for s in specific_suffixes]
        log.info(f"[{region}] Targeted mode: {suffixes}")
    else:
        suffixes = generate_smart_suffixes(region)
        log.info(f"[{region}] Smart mode: {len(suffixes):,} suffixes")

    # Load resume checkpoint
    async with AsyncSessionLocal() as db:
        job = await get_or_create_crawler_job(db, region)
        resume_suffix, resume_num = None, 0
        if job.last_plate:
            lp = job.last_plate.removeprefix(prefix)
            num_str = "".join(c for c in lp if c.isdigit())
            suf_str = "".join(c for c in lp if c.isalpha())
            resume_suffix = suf_str or None
            resume_num    = int(num_str) if num_str else 0
        await update_crawler_job(db, region, status="running", started_at=datetime.utcnow())

    tried = found = 0
    past_resume = (resume_suffix is None)
    _progress[region] = {"tried": 0, "found": 0, "last": "", "status": "running",
                         "current_suffix": "", "suffix_found": 0}

    for suffix in suffixes:
        if not past_resume:
            if suffix == resume_suffix:
                past_resume = True
            else:
                continue

        if _stop_flags.get(region):
            await _checkpoint(region, f"{prefix}0{suffix}", tried, found, "paused")
            return

        kab = get_kabkota_from_suffix(region, suffix)
        consecutive_empty = 0
        suffix_found = 0

        for num in range(num_lo, num_hi + 1):
            # Skip already-tried numbers on resume suffix
            if suffix == resume_suffix and num <= resume_num:
                continue

            if _stop_flags.get(region):
                plate = f"{prefix}{num}{suffix}"
                await _checkpoint(region, plate, tried, found, "paused")
                log.info(f"[{region}] Paused at {plate}")
                return

            plate = f"{prefix}{num}{suffix}"
            hit   = await _try(adapter, plate)

            tried += 1
            if hit:
                found += 1
                suffix_found += 1
                consecutive_empty = 0
                hit.kabkota = kab   # simpan kab/kota dari suffix pattern
                # Save to DB
                async with AsyncSessionLocal() as db:
                    await save_vehicle(db, hit)
                log.info(f"  ✓ {plate} → {hit.merk} {hit.model} {hit.tahun or ''} [{kab}]")
            else:
                consecutive_empty += 1

            # Smart-skip: too many consecutive empty → this suffix is exhausted
            if consecutive_empty >= skip_after:
                log.debug(f"  Skip suffix {suffix} after {skip_after} empty (found={suffix_found})")
                break

            _progress[region] = {
                "tried": tried, "found": found, "last": plate,
                "current_suffix": suffix, "kab": kab,
                "suffix_found": suffix_found,
                "consecutive_empty": consecutive_empty,
                "status": "running",
            }

            if tried % 200 == 0:
                await _checkpoint(region, plate, tried, found, "running")

            await asyncio.sleep(delay)

    await _checkpoint(region, "", tried, found, "done")
    log.info(f"[{region}] DONE tried={tried:,} found={found}")


async def _try(adapter, plate: str):
    """Coba satu plat. Return VehicleInfo jika ditemukan, None jika tidak."""
    try:
        info = await adapter.fetch(plate)
        if info.merk or info.model:
            return info
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.debug(f"  ✗ {plate}: {e}")
    return None


async def _checkpoint(region, plate, tried, found, status):
    async with AsyncSessionLocal() as db:
        await update_crawler_job(db, region, last_plate=plate,
                                 total_tried=tried, total_found=found, status=status)
    if region in _progress:
        _progress[region].update({"tried": tried, "found": found,
                                   "last": plate, "status": status})


# ── Public API ────────────────────────────────────────────────────────────

def start_crawler(region: str, delay: float = 1.0, mode: str = "motor",
                  skip_after: int = 9999, suffixes: list[str] | None = None) -> dict:
    """
    Start crawler.
    skip_after: loncat suffix setelah N angka kosong berturut-turut
                Default 9999 = scan penuh (aman).  Set ke ~500 untuk lebih cepat
                tapi berpotensi melewatkan plat dengan nomor tinggi (e.g. B5651EP).
    suffixes:   daftar suffix spesifik (targeted mode), e.g. ["FCR","ADQ","KK"]
    """
    if region not in CRAWLABLE_REGIONS:
        return {"error": f"'{region}' butuh NIK. Bisa: {sorted(CRAWLABLE_REGIONS)}"}
    if region not in ADAPTERS:
        return {"error": f"Tidak ada adapter untuk '{region}'"}
    if region in _tasks and not _tasks[region].done():
        return {"status": "already_running", **_progress.get(region, {})}

    _stop_flags[region] = False
    _tasks[region] = asyncio.create_task(
        _run(region, delay, mode, skip_after, suffixes)
    )
    lo, hi = get_number_range(region, mode)
    return {
        "status":     "started",
        "region":     region,
        "prefix":     REGION_PREFIX.get(region),
        "mode":       mode,
        "delay_s":    delay,
        "skip_after": skip_after,
        "number_range": f"{lo}–{hi}",
        "targeted":   suffixes or "smart (known kab/kota suffixes first)",
    }


def stop_crawler(region: str) -> dict:
    _stop_flags[region] = True
    return {"status": "stopping", "region": region}


def crawler_status() -> dict:
    return {
        r: {"running": not t.done(), **_progress.get(r, {})}
        for r, t in _tasks.items()
    }


def add_known_suffix(region: str, suffix: str) -> dict:
    from plate_patterns import KABKOTA_MAP
    suffix = suffix.upper()
    fl = suffix[0] if suffix else ""
    if not fl:
        return {"error": "suffix kosong"}
    if region not in KABKOTA_MAP:
        KABKOTA_MAP[region] = {}
    if fl not in KABKOTA_MAP[region]:
        KABKOTA_MAP[region][fl] = f"Unknown (dari suffix {suffix})"
    return {"added": suffix, "first_letter": fl}
