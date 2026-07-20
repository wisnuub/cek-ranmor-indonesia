"""
Cek Ranmor Indonesia — FastAPI Backend
Aggregates vehicle registration data from multiple regional Samsat systems.
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from adapters import ADAPTERS
from cache import get as cache_get, set as cache_set, make_key
from router import get_region_info, REGION_META


# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚗 Cek Ranmor Indonesia API starting up...")
    yield
    print("🛑 Shutting down.")

app = FastAPI(
    title="Cek Ranmor Indonesia",
    description="API agregator cek pajak & data kendaraan bermotor seluruh Indonesia",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────────

class CheckRequest(BaseModel):
    plate: str
    nik: Optional[str] = None


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Cek Ranmor Indonesia API",
        "version": "1.0.0",
        "docs": "/docs",
        "supported_regions": [
            {"code": code, **meta}
            for code, meta in REGION_META.items()
            if meta["supported"]
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/region/{plate}")
async def detect_region(plate: str):
    """Detect which region a plate number belongs to."""
    try:
        info = get_region_info(plate)
        return info
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/check")
async def check_vehicle_get(
    plate: str = Query(..., description="Nomor polisi, e.g. B1234XYZ"),
    nik: Optional[str] = Query(None, description="NIK 16 digit (jika dibutuhkan)"),
):
    return await _do_check(plate, nik)


@app.post("/check")
async def check_vehicle_post(body: CheckRequest):
    return await _do_check(body.plate, body.nik)


async def _do_check(plate: str, nik: Optional[str]):
    if not plate or len(plate.strip()) < 4:
        raise HTTPException(status_code=400, detail="Nomor polisi tidak valid")

    plate = plate.strip().upper()
    nik = nik.strip() if nik else None

    # Detect region
    try:
        region_info = get_region_info(plate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    region_code = region_info["code"]

    # Check if supported
    if not region_info.get("supported"):
        return JSONResponse(
            status_code=202,
            content={
                "status": "unsupported",
                "plate": plate,
                "region": region_info,
                "message": f"Region {region_info['name']} belum didukung. Segera hadir!",
            },
        )

    # Check cache
    cache_key = make_key(plate, nik)
    cached = await cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return cached

    # Get adapter
    adapter = ADAPTERS.get(region_code)
    if not adapter:
        raise HTTPException(status_code=500, detail=f"Adapter untuk {region_code} tidak tersedia")

    # NIK required but not provided?
    if region_info.get("needs_nik") and not nik:
        return JSONResponse(
            status_code=200,
            content={
                "status": "nik_required",
                "plate": plate,
                "region": region_info,
                "message": f"NIK diperlukan untuk cek kendaraan {region_info['name']}",
            },
        )

    # Fetch from Samsat
    vehicle = await adapter.fetch(plate, nik)
    result = {
        "status": "error" if vehicle.errors else "ok",
        "cached": False,
        "plate": plate,
        "region": region_info,
        "data": vehicle.to_dict(),
    }

    # Cache successful results (1 hour)
    if not vehicle.errors:
        await cache_set(cache_key, result)

    return result


@app.get("/regions")
async def list_regions():
    """List all known regions with support status."""
    return [
        {"code": code, **meta}
        for code, meta in REGION_META.items()
    ]
