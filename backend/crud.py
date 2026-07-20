"""Database CRUD operations."""
from typing import Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from models import Vehicle, CrawlerJob
from adapters.base import VehicleInfo


async def save_vehicle(db: AsyncSession, info: VehicleInfo) -> Optional[Vehicle]:
    """Upsert a VehicleInfo result into the vehicles table."""
    if not info.merk and not info.model:
        return None  # Don't save empty results

    # Check if exists
    result = await db.execute(select(Vehicle).where(Vehicle.plate == info.plate))
    existing = result.scalar_one_or_none()

    data = {
        "plate":            info.plate,
        "region":           info.region,
        "region_name":      info.region_name,
        "merk":             info.merk,
        "model":            info.model,
        "tipe":             info.tipe,
        "tahun":            info.tahun,
        "warna":            info.warna,
        "jenis":            info.jenis,
        "bahan_bakar":      info.bahan_bakar,
        "cc":               info.cc,
        "pkb_pokok":        info.pkb_pokok,
        "pkb_denda":        info.pkb_denda,
        "swdkllj_pokok":    info.swdkllj_pokok,
        "swdkllj_denda":    info.swdkllj_denda,
        "total_tagihan":    info.total_tagihan,
        "jatuh_tempo_pajak": info.jatuh_tempo_pajak,
        "jatuh_tempo_stnk":  info.jatuh_tempo_stnk,
        "status_pajak":      info.status_pajak,
        "nama_pemilik":      info.nama_pemilik,
        "alamat":            info.alamat,
    }

    if existing:
        for k, v in data.items():
            if v is not None:
                setattr(existing, k, v)
        await db.commit()
        return existing
    else:
        v = Vehicle(**data)
        db.add(v)
        await db.commit()
        await db.refresh(v)
        return v


async def search_vehicles(
    db: AsyncSession,
    q: Optional[str] = None,
    region: Optional[str] = None,
    merk: Optional[str] = None,
    jenis: Optional[str] = None,
    tahun_min: Optional[int] = None,
    tahun_max: Optional[int] = None,
    warna: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(Vehicle)
    count_stmt = select(func.count()).select_from(Vehicle)

    filters = []

    # Full-text search across merk + model + tipe
    if q:
        terms = q.strip().split()
        for term in terms:
            pat = f"%{term}%"
            filters.append(
                or_(
                    Vehicle.merk.ilike(pat),
                    Vehicle.model.ilike(pat),
                    Vehicle.tipe.ilike(pat),
                )
            )

    if region:
        filters.append(Vehicle.region == region)
    if merk:
        filters.append(Vehicle.merk.ilike(f"%{merk}%"))
    if jenis:
        filters.append(Vehicle.jenis.ilike(f"%{jenis}%"))
    if warna:
        filters.append(Vehicle.warna.ilike(f"%{warna}%"))
    if tahun_min:
        filters.append(Vehicle.tahun >= tahun_min)
    if tahun_max:
        filters.append(Vehicle.tahun <= tahun_max)

    if filters:
        from sqlalchemy import and_
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Vehicle.updated_at.desc()).limit(limit).offset(offset)
    rows = await db.execute(stmt)
    vehicles = rows.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [v.to_dict() for v in vehicles],
    }


async def get_db_stats(db: AsyncSession) -> dict:
    total = await db.execute(select(func.count()).select_from(Vehicle))
    by_region = await db.execute(
        select(Vehicle.region, Vehicle.region_name, func.count().label("count"))
        .group_by(Vehicle.region, Vehicle.region_name)
        .order_by(func.count().desc())
    )
    by_merk = await db.execute(
        select(Vehicle.merk, func.count().label("count"))
        .where(Vehicle.merk.isnot(None))
        .group_by(Vehicle.merk)
        .order_by(func.count().desc())
        .limit(20)
    )
    return {
        "total_vehicles": total.scalar() or 0,
        "by_region": [{"region": r, "name": n, "count": c} for r, n, c in by_region],
        "top_merks": [{"merk": m, "count": c} for m, c in by_merk],
    }


# ── Crawler Job ─────────────────────────────────────────────────────

async def get_or_create_crawler_job(db: AsyncSession, region: str) -> CrawlerJob:
    result = await db.execute(select(CrawlerJob).where(CrawlerJob.region == region))
    job = result.scalar_one_or_none()
    if not job:
        job = CrawlerJob(region=region)
        db.add(job)
        await db.commit()
        await db.refresh(job)
    return job


async def update_crawler_job(db: AsyncSession, region: str, **kwargs):
    result = await db.execute(select(CrawlerJob).where(CrawlerJob.region == region))
    job = result.scalar_one_or_none()
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
        await db.commit()
