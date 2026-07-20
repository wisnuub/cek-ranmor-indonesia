"""SQLAlchemy ORM models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, func, Index
)
from database import Base


class Vehicle(Base):
    """Accumulated vehicle records from queries & crawler."""
    __tablename__ = "vehicles"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    plate       = Column(String(20),  unique=True, nullable=False)
    region      = Column(String(50),  nullable=False)
    region_name = Column(String(100))

    # Kendaraan
    merk        = Column(String(100))
    model       = Column(String(200))
    tipe        = Column(String(200))
    tahun       = Column(Integer)
    warna       = Column(String(100))
    jenis       = Column(String(100))
    bahan_bakar = Column(String(50))
    cc          = Column(String(20))

    # Pajak
    pkb_pokok        = Column(Integer)
    pkb_denda        = Column(Integer)
    swdkllj_pokok    = Column(Integer)
    swdkllj_denda    = Column(Integer)
    total_tagihan    = Column(Integer)
    jatuh_tempo_pajak = Column(String(50))
    jatuh_tempo_stnk  = Column(String(50))
    status_pajak      = Column(String(50))

    # Kepemilikan (hashed for privacy)
    nama_pemilik = Column(String(200))
    alamat       = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_vehicles_region",        "region"),
        Index("ix_vehicles_merk_model",    "merk", "model"),
        Index("ix_vehicles_tahun",         "tahun"),
        Index("ix_vehicles_jenis",         "jenis"),
    )

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class CrawlerJob(Base):
    """Tracks crawler progress per region."""
    __tablename__ = "crawler_jobs"

    id          = Column(Integer, primary_key=True)
    region      = Column(String(50), unique=True, nullable=False)
    status      = Column(String(20), default="idle")   # idle/running/paused/done
    total_tried = Column(Integer, default=0)
    total_found = Column(Integer, default=0)
    last_plate  = Column(String(20))                   # resume checkpoint
    started_at  = Column(DateTime)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
