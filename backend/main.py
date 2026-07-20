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
from plate_patterns import KNOWN_SUFFIXES, REGION_PRIMARY_PREFIX

ADMIN_KEY = os.getenv("ADMIN_KEY", "ranmor-admin-2025")


# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("🚗 Cek Ranmor Indonesia API ready")
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
        return JSONResponse(202, {
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
        return JSONResponse(200, {
            "status": "nik_required",
            "plate": plate,
            "region": region_info,
            "message": f"NIK diperlukan untuk cek kendaraan {region_info['name']}",
        })

    vehicle = await adapter.fetch(plate, nik)

    result = {
        "status": "error" if vehicle.errors else "ok",
        "cached": False,
        "plate": plate,
        "region": region_info,
        "data": vehicle.to_dict(),
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
    q:        Optional[str] = Query(None, description="Keyword: merk/model/tipe, e.g. 'XSR 155'"),
    region:   Optional[str] = Query(None, description="Kode region: bali, jakarta, jabar..."),
    merk:     Optional[str] = Query(None),
    jenis:    Optional[str] = Query(None, description="Sepeda Motor / Mobil Penumpang / dll"),
    warna:    Optional[str] = Query(None),
    tahun_min: Optional[int] = Query(None),
    tahun_max: Optional[int] = Query(None),
    limit:    int = Query(50, le=200),
    offset:   int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Search vehicles in the accumulated database."""
    if not any([q, region, merk, jenis, warna, tahun_min, tahun_max]):
        raise HTTPException(400, "Masukkan minimal satu parameter pencarian")

    return await search_vehicles(
        db, q=q, region=region, merk=merk, jenis=jenis,
        warna=warna, tahun_min=tahun_min, tahun_max=tahun_max,
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
# Admin — Crawler management
# ──────────────────────────────────────────────

@app.post("/admin/crawler/start")
async def crawler_start(
    region: str   = Query(..., description="Region: bali, jabar, jateng, diy"),
    delay:  float = Query(1.5, description="Detik antar request (jangan terlalu cepat)"),
    mode:   str   = Query("all", description="all | motor | mobil"),
    _: None = Depends(require_admin),
):
    """
    Start smart plate crawler untuk satu region.
    Phase 1: coba known suffixes dulu (cepat).
    Phase 2: brute-force sisa kombinasi.
    """
    return start_crawler(region, delay=delay, mode=mode)


@app.post("/admin/crawler/stop")
async def crawler_stop(
    region: str = Query(...),
    _: None = Depends(require_admin),
):
    return stop_crawler(region)


@app.get("/admin/crawler/status")
async def crawler_status_endpoint(_: None = Depends(require_admin)):
    return {
        "active":            crawler_status(),
        "crawlable_regions": list(CRAWLABLE_REGIONS),
        "known_suffixes": {
            r: len(s) for r, s in KNOWN_SUFFIXES.items()
        },
        "prefixes": REGION_PRIMARY_PREFIX,
    }


@app.post("/admin/crawler/suffix")
async def add_suffix(
    region: str = Query(...),
    suffix: str = Query(..., description="Suffix baru, e.g. FCR, ADQ, KK"),
    _: None = Depends(require_admin),
):
    """Tambahkan suffix yang diketahui valid ke database pattern."""
    result = add_known_suffix(region, suffix)
    return result


@app.get("/admin/crawler/suffixes/{region}")
async def list_suffixes(region: str, _: None = Depends(require_admin)):
    """Lihat daftar known suffixes untuk satu region."""
    return {
        "region":  region,
        "count":   len(KNOWN_SUFFIXES.get(region, [])),
        "suffixes": KNOWN_SUFFIXES.get(region, []),
    }
