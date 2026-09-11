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
import subprocess
from datetime import datetime
from pathlib import Path

from database import AsyncSessionLocal
from crud import save_vehicle, get_or_create_crawler_job, update_crawler_job
from adapters import ADAPTERS
from router import REGION_META
from plate_patterns import (
    generate_smart_suffixes, get_number_range,
    get_kabkota_from_suffix, get_region_prefixes,
)

log = logging.getLogger("crawler")

CRAWLABLE_REGIONS = {"jabar", "jateng", "diy", "bali", "jakarta"}

_tasks:         dict[str, asyncio.Task] = {}
_stop_flags:    dict[str, bool]         = {}
_stop_reasons:  dict[str, str]          = {}   # job_key -> "paused" | "replaced" | ...
_progress:      dict[str, dict]         = {}
_chunk_cursor:  dict[str, int]          = {}   # auto-chain: next unclaimed number per region


def _friendly_name(region: str, lo: int | None = None, hi: int | None = None) -> str:
    """Nama enak dibaca untuk satu worker crawler, e.g. 'Jawa Tengah (1500-3333)'."""
    base = REGION_META.get(region, {}).get("name", region.upper())
    if lo is not None and hi is not None:
        return f"{base} ({lo}-{hi})"
    return base


def _claim_next_chunk(region: str, chunk_size: int, max_num: int) -> tuple[int, int] | None:
    """Ambil slice angka berikutnya yang belum diklaim untuk region ini (auto-chain)."""
    lo = _chunk_cursor.get(region)
    if lo is None or lo > max_num:
        return None
    hi = min(lo + chunk_size - 1, max_num)
    _chunk_cursor[region] = hi + 1
    return (lo, hi)


def _reserve_range(region: str, lo: int, hi: int):
    """Tandai range ini sudah 'diambil' supaya auto-chain berikutnya mulai setelah hi."""
    current = _chunk_cursor.get(region)
    if current is None or hi + 1 > current:
        _chunk_cursor[region] = hi + 1


async def _run(region: str, delay: float, mode: str,
               skip_after: int, specific_suffixes: list[str] | None,
               num_range: tuple[int, int] | None = None, job_key: str | None = None,
               auto_chain: bool = False, chunk_size: int = 1000, max_num: int = 9999):
    job_key  = job_key or region
    adapter  = ADAPTERS.get(region)
    prefixes = get_region_prefixes(region)   # e.g. jateng → ["H","G","K","R"]
    if not adapter or not prefixes:
        log.error(f"[{region}] No adapter/prefix"); return

    num_lo, num_hi = num_range if num_range else get_number_range(region, mode)

    # Load resume checkpoint — cari prefix mana yang cocok dengan last_plate
    async with AsyncSessionLocal() as db:
        job = await get_or_create_crawler_job(db, job_key)
        resume_prefix, resume_suffix, resume_num = None, None, 0
        if job.last_plate:
            lp = job.last_plate
            matched = next((p for p in prefixes if lp.startswith(p)), None)
            if matched:
                resume_prefix = matched
                rest    = lp.removeprefix(matched)
                num_str = "".join(c for c in rest if c.isdigit())
                suf_str = "".join(c for c in rest if c.isalpha())
                resume_suffix = suf_str or None
                resume_num    = int(num_str) if num_str else 0
        await update_crawler_job(db, job_key, status="running", started_at=datetime.utcnow())

    tried = found = 0
    _progress[job_key] = {"tried": 0, "found": 0, "last": "", "status": "running",
                         "current_suffix": "", "suffix_found": 0, "region": region,
                         "range": f"{num_lo}-{num_hi}",
                         "name": _friendly_name(region, num_lo, num_hi)}

    while True:
        past_resume_prefix = (resume_prefix is None)

        for prefix in prefixes:
            if not past_resume_prefix:
                if prefix == resume_prefix:
                    past_resume_prefix = True
                else:
                    continue

            # Suffix list: specific (user-provided) atau smart-generated (per-prefix untuk jateng)
            if specific_suffixes:
                suffixes = [s.upper() for s in specific_suffixes]
                log.info(f"[{region}/{prefix}] Targeted mode: {suffixes}")
            else:
                suffixes = generate_smart_suffixes(region, prefix)
                log.info(f"[{region}/{prefix}] Smart mode: {len(suffixes):,} suffixes")

            on_resume_prefix = (prefix == resume_prefix)
            past_resume_suffix = not on_resume_prefix or (resume_suffix is None)

            for suffix in suffixes:
                if not past_resume_suffix:
                    if suffix == resume_suffix:
                        past_resume_suffix = True
                    else:
                        continue

                if _stop_flags.get(job_key):
                    reason = _stop_reasons.get(job_key, "paused")
                    await _checkpoint(job_key, f"{prefix}0{suffix}", tried, found, reason)
                    return

                kab = get_kabkota_from_suffix(region, suffix, prefix)
                consecutive_empty = 0
                suffix_found = 0
                on_resume_suffix = on_resume_prefix and (suffix == resume_suffix)

                for num in range(num_lo, num_hi + 1):
                    # Skip already-tried numbers on resume suffix
                    if on_resume_suffix and num <= resume_num:
                        continue

                    if _stop_flags.get(job_key):
                        plate = f"{prefix}{num}{suffix}"
                        reason = _stop_reasons.get(job_key, "paused")
                        await _checkpoint(job_key, plate, tried, found, reason)
                        log.info(f"[{job_key}] Stopped ({reason}) at {plate}")
                        return

                    plate = f"{prefix}{num}{suffix}"
                    hit, needs_relogin = await _try(adapter, plate)

                    # Token Jakarta expired → refresh dan coba lagi
                    if needs_relogin and region == "jakarta":
                        log.warning("[jakarta] Token expired saat crawl — mencoba refresh...")
                        refreshed = await _refresh_jakarta_token()
                        if refreshed:
                            hit, needs_relogin = await _try(adapter, plate)
                        if needs_relogin or not refreshed:
                            await _checkpoint(job_key, plate, tried, found, "token expired")
                            log.error("[jakarta] Tidak bisa refresh token. Crawl dihentikan.")
                            _progress[job_key]["status"] = "token expired"
                            return

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

                    _progress[job_key] = {
                        "tried": tried, "found": found, "last": plate,
                        "current_prefix": prefix, "current_suffix": suffix, "kab": kab,
                        "suffix_found": suffix_found,
                        "consecutive_empty": consecutive_empty,
                        "status": "running",
                        "region": region,
                        "range": f"{num_lo}-{num_hi}",
                        "name": _friendly_name(region, num_lo, num_hi),
                    }

                    if tried % 200 == 0:
                        await _checkpoint(job_key, plate, tried, found, "running")

                    await asyncio.sleep(delay)

        # Satu chunk (semua prefix/suffix/nomor di range num_lo-num_hi) selesai
        log.info(f"[{job_key}] Chunk {num_lo}-{num_hi} selesai — tried={tried:,} found={found}")

        if not auto_chain:
            break

        nxt = _claim_next_chunk(region, chunk_size, max_num)
        if not nxt:
            log.info(f"[{job_key}] Tidak ada chunk lagi (sudah sampai {max_num}) — worker selesai")
            break

        num_lo, num_hi = nxt
        resume_prefix, resume_suffix, resume_num = None, None, 0
        _progress[job_key] = {"tried": tried, "found": found, "last": "", "status": "running",
                              "current_suffix": "", "suffix_found": 0, "region": region,
                              "range": f"{num_lo}-{num_hi}",
                              "name": _friendly_name(region, num_lo, num_hi)}
        async with AsyncSessionLocal() as db:
            await update_crawler_job(db, job_key, status="running", last_plate="")
        log.info(f"[{job_key}] Auto-chain: lanjut ke chunk berikutnya {num_lo}-{num_hi}")

    await _checkpoint(job_key, "", tried, found, "completed")
    log.info(f"[{job_key}] COMPLETED tried={tried:,} found={found}")


async def _try(adapter, plate: str) -> tuple:
    """
    Coba satu plat.
    Return (VehicleInfo, needs_relogin) — VehicleInfo None jika tidak ditemukan.
    """
    try:
        info = await adapter.fetch(plate)
        if getattr(info, "needs_relogin", False):
            return None, True
        if info.merk or info.model:
            return info, False
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.debug(f"  ✗ {plate}: {e}")
    return None, False


async def _refresh_jakarta_token() -> bool:
    """Jalankan jakarta_refresh_token.py untuk refresh Google ID token."""
    script = Path(__file__).parent / "jakarta_refresh_token.py"
    if not script.exists():
        log.warning("[jakarta] Script refresh tidak ditemukan: %s", script)
        return False
    try:
        result = subprocess.run(
            ["python", str(script)],
            capture_output=True, text=True, timeout=30
        )
        ok = result.returncode == 0
        if ok:
            log.info("[jakarta] Token berhasil di-refresh")
        else:
            log.warning("[jakarta] Refresh gagal: %s", result.stdout[-200:])
        return ok
    except Exception as e:
        log.warning("[jakarta] Refresh error: %s", e)
        return False


async def _checkpoint(job_key, plate, tried, found, status):
    async with AsyncSessionLocal() as db:
        await update_crawler_job(db, job_key, last_plate=plate,
                                 total_tried=tried, total_found=found, status=status)
    if job_key in _progress:
        _progress[job_key].update({"tried": tried, "found": found,
                                   "last": plate, "status": status})


# ── Public API ────────────────────────────────────────────────────────────

def start_crawler(region: str, delay: float = 1.0, mode: str = "default",
                  skip_after: int = 9999, suffixes: list[str] | None = None,
                  num_range: tuple[int, int] | None = None,
                  auto_chain: bool = False, chunk_size: int = 1000, max_num: int = 9999) -> dict:
    """
    Start crawler.
    skip_after: loncat suffix setelah N angka kosong berturut-turut
                Default 9999 = scan penuh (aman).  Set ke ~500 untuk lebih cepat
                tapi berpotensi melewatkan plat dengan nomor tinggi (e.g. B5651EP).
    suffixes:   daftar suffix spesifik (targeted mode), e.g. ["FCR","ADQ","KK"]
    num_range:  (lo, hi) override eksplisit untuk range angka — dipakai untuk
                menjalankan beberapa worker paralel pada region yang sama,
                masing-masing dengan slice angka berbeda (lihat job_key di bawah).
                Kalau diisi, job ini punya job_key sendiri "{region}:{lo}-{hi}"
                sehingga tidak bentrok dengan job region biasa atau slice lain.
    auto_chain: kalau True, begitu worker ini selesai dengan slice-nya sendiri,
                dia otomatis ambil slice berikutnya yang belum diklaim (chunk_size
                per slice) dari cursor bersama per-region, terus lanjut sampai max_num.
                Beberapa worker auto_chain di region yang sama akan saling berbagi
                cursor ini jadi tidak akan rebutan/overlap slice yang sama.
    chunk_size: besar slice untuk auto-chain (default 1000, e.g. 4001-5000).
    max_num:    batas atas nomor plat untuk auto-chain (default 9999).

    CATATAN JAKARTA:
    - Delay minimum yang disarankan: 2.5 detik (WAF rate limit ~30-40 req/menit)
    - Token Google expired tiap 1 jam — pastikan HP tersambung via ADB
    - Jalankan `python backend/jakarta_refresh_token.py` sebelum crawl
    """
    if region not in CRAWLABLE_REGIONS:
        return {"error": f"'{region}' butuh NIK. Bisa: {sorted(CRAWLABLE_REGIONS)}"}
    if region not in ADAPTERS:
        return {"error": f"Tidak ada adapter untuk '{region}'"}

    # Jakarta: cek token validity sebelum mulai
    if region == "jakarta":
        from adapters.jakarta import _load_session, _get_id_token, _token_is_valid
        sess = _load_session()
        tok  = _get_id_token(sess) if sess else None
        if not tok or not _token_is_valid(tok):
            return {
                "error": "Token Jakarta expired/tidak ada. "
                         "Jalankan: python backend/jakarta_refresh_token.py",
                "hint":  "Sambungkan HP via ADB terlebih dahulu",
            }
        if delay < 2.5:
            delay = 2.5  # paksa minimal delay untuk hindari WAF block

    if num_range:
        lo, hi = num_range
        if lo > hi:
            return {"error": f"Range tidak valid: {lo}-{hi}"}
        job_key = f"{region}:{lo}-{hi}"
        if auto_chain:
            _reserve_range(region, lo, hi)
    else:
        lo, hi = get_number_range(region, mode)
        job_key = region
        if auto_chain:
            _reserve_range(region, lo, hi)

    if job_key in _tasks and not _tasks[job_key].done():
        return {"status": "already_running", **_progress.get(job_key, {})}

    _stop_flags[job_key] = False
    _tasks[job_key] = asyncio.create_task(
        _run(region, delay, mode, skip_after, suffixes,
             num_range=(lo, hi) if num_range else None, job_key=job_key,
             auto_chain=auto_chain, chunk_size=chunk_size, max_num=max_num)
    )
    return {
        "status":     "started",
        "job_key":    job_key,
        "region":     region,
        "prefixes":   get_region_prefixes(region),
        "mode":       mode,
        "delay_s":    delay,
        "skip_after": skip_after,
        "number_range": f"{lo}–{hi}",
        "auto_chain": auto_chain,
        "chunk_size": chunk_size if auto_chain else None,
        "max_num":    max_num if auto_chain else None,
        "targeted":   suffixes or "smart (known kab/kota suffixes first)",
    }


async def stop_crawler(region: str, num_range: tuple[int, int] | None = None,
                       reason: str = "paused") -> dict:
    """
    Stop satu worker crawler.
    reason: label status yang disimpan — "paused" (bisa di-resume normal) atau
            "replaced" (worker ini sengaja diganti/digantikan worker lain dan
            tidak akan di-resume lewat alur biasa), atau label bebas lainnya.
    """
    job_key = f"{region}:{num_range[0]}-{num_range[1]}" if num_range else region
    _stop_flags[job_key] = True
    _stop_reasons[job_key] = reason

    task = _tasks.get(job_key)
    if not task or task.done():
        # Worker sudah berhenti sebelumnya — tidak ada loop yang akan checkpoint
        # sendiri, jadi update status-nya langsung di sini.
        if job_key in _progress:
            _progress[job_key]["status"] = reason
        async with AsyncSessionLocal() as db:
            await update_crawler_job(db, job_key, status=reason)

    return {"status": "stopping", "job_key": job_key, "reason": reason}


def _parse_job_key(job_key: str) -> tuple[str, int | None, int | None]:
    if ":" in job_key:
        region, rng = job_key.split(":", 1)
        try:
            lo_s, hi_s = rng.split("-", 1)
            return region, int(lo_s), int(hi_s)
        except ValueError:
            return region, None, None
    return job_key, None, None


def crawler_status() -> dict:
    return {
        r: {"running": not t.done(), **_progress.get(r, {})}
        for r, t in _tasks.items()
    }


async def crawler_status_full(db) -> dict:
    """
    Status semua job — termasuk yang tidak lagi di-track di memory (misal setelah
    restart server) tapi masih punya riwayat di DB, e.g. job yang di-'replaced'
    atau 'completed' sebelum restart terakhir. Supaya label statusnya tetap
    kelihatan walau workernya sudah tidak jalan lagi.
    """
    from crud import list_crawler_jobs
    live   = crawler_status()
    result = dict(live)
    rows   = await list_crawler_jobs(db)
    for job in rows:
        if job.region in result:
            continue
        region, lo, hi = _parse_job_key(job.region)
        result[job.region] = {
            "running": False,
            "tried":   job.total_tried or 0,
            "found":   job.total_found or 0,
            "last":    job.last_plate or "",
            "status":  job.status,
            "region":  region,
            "range":   f"{lo}-{hi}" if lo is not None else None,
            "name":    _friendly_name(region, lo, hi),
        }
    return result


def add_known_suffix(region: str, suffix: str, prefix: str | None = None) -> dict:
    from plate_patterns import KABKOTA_MAP, JATENG_KABKOTA_BY_PREFIX
    suffix = suffix.upper()
    fl = suffix[0] if suffix else ""
    if not fl:
        return {"error": "suffix kosong"}

    if region == "jateng" and prefix:
        prefix = prefix.upper()
        table = JATENG_KABKOTA_BY_PREFIX.setdefault(prefix, {})
    else:
        table = KABKOTA_MAP.setdefault(region, {})

    if fl not in table:
        table[fl] = f"Unknown (dari suffix {suffix})"
    return {"added": suffix, "first_letter": fl, "prefix": prefix}
