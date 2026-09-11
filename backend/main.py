"""
Cek Ranmor Indonesia — FastAPI Backend
"""
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from adapters import ADAPTERS
from cache import get as cache_get, set as cache_set, make_key
from router import get_region_info, REGION_META
from database import get_db, init_db
from crud import save_vehicle, search_vehicles, get_db_stats
from crawler import start_crawler, stop_crawler, crawler_status, add_known_suffix, CRAWLABLE_REGIONS
from plate_patterns import KNOWN_SUFFIXES, REGION_PRIMARY_PREFIX, JATENG_KABKOTA_BY_PREFIX, get_region_prefixes

ADMIN_KEY = os.getenv("ADMIN_KEY", "ranmor-admin-2025")


# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Cek Ranmor Indonesia API ready")

    # ── Auto-start crawler ───────────────────────────────────────────
    # Set env AUTO_CRAWL_REGIONS="jabar,jateng,diy,bali" untuk aktifkan
    auto_env = os.getenv("AUTO_CRAWL_REGIONS", "")
    if auto_env.strip():
        auto_delay  = float(os.getenv("CRAWL_DELAY",      "1.2"))
        auto_mode   = os.getenv("CRAWL_MODE",             "all")
        auto_skip   = int(os.getenv("CRAWL_SKIP_AFTER",   "9999"))
        for region in [r.strip() for r in auto_env.split(",") if r.strip()]:
            if region not in CRAWLABLE_REGIONS:
                print(f"  [AUTO-CRAWL] '{region}' bukan region yang bisa di-crawl, skip")
                continue
            result = start_crawler(region, delay=auto_delay, mode=auto_mode, skip_after=auto_skip)
            status = result.get("status", "?")
            print(f"  [AUTO-CRAWL] {region}: {status} (delay={auto_delay}s, mode={auto_mode})")

    yield

app = FastAPI(
    title="Cek Ranmor Indonesia",
    description="API agregator cek pajak & data kendaraan bermotor seluruh Indonesia",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Auth helper
# ──────────────────────────────────────────────

def require_admin(x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

class CheckRequest(BaseModel):
    plate: str
    nik: Optional[str] = None


# ──────────────────────────────────────────────
# Core routes
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Cek Ranmor Indonesia API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "check":   "/check?plate=B1234XYZ",
            "search":  "/search?q=XSR+155&region=bali",
            "stats":   "/stats",
            "regions": "/regions",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/region/{plate}")
async def detect_region(plate: str):
    try:
        return get_region_info(plate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ──────────────────────────────────────────────
# Check vehicle
# ──────────────────────────────────────────────

@app.get("/check")
async def check_get(
    plate: str = Query(...),
    nik: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _do_check(plate, nik, db)


@app.post("/check")
async def check_post(body: CheckRequest, db: AsyncSession = Depends(get_db)):
    return await _do_check(body.plate, body.nik, db)


async def _do_check(plate: str, nik: Optional[str], db: AsyncSession):
    if not plate or len(plate.strip()) < 4:
        raise HTTPException(400, "Nomor polisi tidak valid")

    plate = plate.strip().upper()
    nik   = nik.strip() if nik else None

    try:
        region_info = get_region_info(plate)
    except ValueError as e:
        raise HTTPException(400, str(e))

    region_code = region_info["code"]

    if not region_info.get("supported"):
        return JSONResponse(status_code=202, content={
            "status": "unsupported",
            "plate": plate,
            "region": region_info,
            "message": f"Region {region_info['name']} belum didukung. Segera hadir!",
        })

    cache_key = make_key(plate, nik)
    cached = await cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    adapter = ADAPTERS.get(region_code)
    if not adapter:
        raise HTTPException(500, f"Adapter untuk {region_code} tidak tersedia")

    if region_info.get("needs_nik") and not nik:
        return JSONResponse(status_code=200, content={
            "status": "nik_required",
            "plate": plate,
            "region": region_info,
            "message": f"NIK diperlukan untuk cek kendaraan {region_info['name']}",
        })

    vehicle = await adapter.fetch(plate, nik)

    result = {
        "status":        "relogin_required" if vehicle.needs_relogin
                         else ("error" if vehicle.errors else "ok"),
        "cached":        False,
        "plate":         plate,
        "region":        region_info,
        "data":          vehicle.to_dict(),
    }

    # Auto-save successful results to DB
    if not vehicle.errors:
        await cache_set(cache_key, result)
        await save_vehicle(db, vehicle)

    return result


# ──────────────────────────────────────────────
# Search / Browse database
# ──────────────────────────────────────────────

@app.get("/search")
async def search(
    q:         Optional[str] = Query(None, description="Keyword: merk/model/tipe, e.g. 'XSR 155'"),
    region:    Optional[str] = Query(None, description="Kode region: bali, jakarta, jabar..."),
    merk:      Optional[str] = Query(None),
    jenis:     Optional[str] = Query(None, description="Sepeda Motor / Mobil Penumpang / dll"),
    warna:     Optional[str] = Query(None),
    kabkota:   Optional[str] = Query(None, description="Kabupaten/kota, e.g. 'Kota Bandung'"),
    tahun_min: Optional[int] = Query(None),
    tahun_max: Optional[int] = Query(None),
    limit:     int = Query(50, le=200),
    offset:    int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Search vehicles in the accumulated database."""
    if not any([q, region, merk, jenis, warna, kabkota, tahun_min, tahun_max]):
        raise HTTPException(400, "Masukkan minimal satu parameter pencarian")

    return await search_vehicles(
        db, q=q, region=region, merk=merk, jenis=jenis,
        warna=warna, kabkota=kabkota,
        tahun_min=tahun_min, tahun_max=tahun_max,
        limit=limit, offset=offset,
    )


@app.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    """Database statistics."""
    return await get_db_stats(db)


@app.get("/regions")
async def list_regions():
    return [{"code": code, **meta} for code, meta in REGION_META.items()]


# ──────────────────────────────────────────────
# Public crawler status (read-only, no auth)
# ──────────────────────────────────────────────

@app.get("/crawler/status")
async def public_crawler_status(db: AsyncSession = Depends(get_db)):
    """Status crawler publik — tidak butuh admin key."""
    from crud import get_db_stats
    from crawler import crawler_status_full
    status = await crawler_status_full(db)
    stats  = await get_db_stats(db)
    return {
        "crawlers": status,
        "db": stats,
    }


# ──────────────────────────────────────────────
# Admin — Crawler management
# ──────────────────────────────────────────────

@app.post("/admin/crawler/start")
async def crawler_start(
    region:     str   = Query(..., description="Region: bali, jabar, jateng, diy"),
    delay:      float = Query(1.5, description="Detik antar request (jangan terlalu cepat)"),
    mode:       str   = Query("default", description="default (1500-6999) | all | motor | mobil | bus | barang | khusus"),
    skip_after: int   = Query(9999, description="Skip suffix setelah N angka kosong berturut-turut (default 9999 = scan penuh)"),
    num_lo:     Optional[int] = Query(None, description="Override: angka mulai (untuk jalankan beberapa worker paralel per-slice)"),
    num_hi:     Optional[int] = Query(None, description="Override: angka akhir (wajib diisi bareng num_lo)"),
    auto_chain: bool  = Query(False, description="Kalau selesai satu slice, otomatis lanjut ambil slice berikutnya yang belum diklaim sampai max_num"),
    chunk_size: int   = Query(1000, description="Besar tiap slice untuk auto_chain, e.g. 1000 → 4001-5000, 5001-6000, ..."),
    max_num:    int   = Query(9999, description="Batas atas nomor plat untuk auto_chain"),
    _: None = Depends(require_admin),
):
    """
    Start smart plate crawler untuk satu region.
    Phase 1: coba known suffixes dulu (cepat).
    Phase 2: brute-force sisa kombinasi.

    Untuk jalankan beberapa worker paralel pada region yang sama, isi num_lo/num_hi
    dengan slice angka yang berbeda-beda per request, misal:
      /admin/crawler/start?region=jateng&num_lo=1500&num_hi=2999&auto_chain=true
      /admin/crawler/start?region=jateng&num_lo=3000&num_hi=4000&auto_chain=true
    Tiap slice punya job_key & checkpoint sendiri jadi tidak saling bentrok. Dengan
    auto_chain=true, begitu satu worker selesai dengan slice-nya, dia otomatis ambil
    slice kosong berikutnya (misal 4001-5000, lalu 5001-6000, dst) dari cursor bersama
    per-region, sampai max_num — semua worker auto_chain di region yang sama berbagi
    cursor ini jadi tidak akan rebutan slice yang sama.
    """
    num_range = (num_lo, num_hi) if num_lo is not None and num_hi is not None else None
    return start_crawler(region, delay=delay, mode=mode, skip_after=skip_after,
                          num_range=num_range, auto_chain=auto_chain,
                          chunk_size=chunk_size, max_num=max_num)


@app.post("/admin/crawler/stop")
async def crawler_stop(
    region: str = Query(...),
    num_lo:  Optional[int] = Query(None),
    num_hi:  Optional[int] = Query(None),
    reason:  str = Query("paused", description="paused (bisa di-resume) | replaced (diganti worker lain) | label bebas"),
    _: None = Depends(require_admin),
):
    num_range = (num_lo, num_hi) if num_lo is not None and num_hi is not None else None
    return await stop_crawler(region, num_range=num_range, reason=reason)


@app.get("/admin/crawler/status")
async def crawler_status_endpoint(_: None = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from crawler import crawler_status_full
    known_suffixes = {r: len(s) for r, s in KNOWN_SUFFIXES.items()}
    known_suffixes["jateng"] = sum(len(s) for s in JATENG_KABKOTA_BY_PREFIX.values())
    return {
        "active":            await crawler_status_full(db),
        "crawlable_regions": list(CRAWLABLE_REGIONS),
        "known_suffixes":    known_suffixes,
        "prefixes": {
            **REGION_PRIMARY_PREFIX,
            "jateng": get_region_prefixes("jateng"),
        },
    }


@app.get("/admin/jakarta/token-status")
async def jakarta_token_status(_: None = Depends(require_admin)):
    """Cek status Google ID token untuk Jakarta adapter."""
    from adapters.jakarta import _load_session, _get_id_token, _token_is_valid
    import base64, json, time
    sess = _load_session()
    if not sess:
        return {"status": "no_session", "message": "jakarta_session.json tidak ada"}
    token = _get_id_token(sess)
    if not token:
        return {"status": "no_token", "message": "Token tidak ditemukan di session"}
    valid = _token_is_valid(token)
    try:
        parts = token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(padded))
        exp = payload.get("exp", 0)
        remaining = max(0, exp - int(time.time()))
        expires_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp))
    except Exception:
        remaining = 0
        expires_at = "unknown"
    return {
        "status":      "valid" if valid else "expired",
        "valid":       valid,
        "expires_at":  expires_at,
        "remaining_s": remaining,
        "remaining_m": remaining // 60,
        "refreshed_at": sess.get("refreshed_at"),
        "message":     "OK" if valid else (
            "Token expired — jalankan: python backend/jakarta_refresh_token.py"
        ),
    }


@app.post("/admin/crawler/suffix")
async def add_suffix(
    region: str = Query(...),
    suffix: str = Query(..., description="Suffix baru, e.g. FCR, ADQ, KK"),
    prefix: Optional[str] = Query(None, description="Kode plat (wajib untuk jateng: H/G/K/R)"),
    _: None = Depends(require_admin),
):
    """Tambahkan suffix yang diketahui valid ke database pattern."""
    result = add_known_suffix(region, suffix, prefix)
    return result


@app.get("/admin/crawler/suffixes/{region}")
async def list_suffixes(region: str, _: None = Depends(require_admin)):
    """Lihat daftar known suffixes untuk satu region."""
    if region == "jateng":
        return {
            "region": region,
            "prefixes": {
                p: {"count": len(s), "suffixes": s}
                for p, s in JATENG_KABKOTA_BY_PREFIX.items()
            },
        }
    return {
        "region":  region,
        "count":   len(KNOWN_SUFFIXES.get(region, [])),
        "suffixes": KNOWN_SUFFIXES.get(region, []),
    }
