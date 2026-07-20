"""Base adapter class and shared data model."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VehicleInfo:
    # Core
    plate: str
    region: str
    region_name: str

    # Kendaraan
    merk: Optional[str] = None
    model: Optional[str] = None
    tipe: Optional[str] = None
    tahun: Optional[int] = None
    warna: Optional[str] = None
    jenis: Optional[str] = None       # Sepeda Motor / Mobil Penumpang / dll
    bahan_bakar: Optional[str] = None
    cc: Optional[str] = None

    # Pajak & STNK
    pkb_pokok: Optional[int] = None       # Pajak Kendaraan Bermotor (Rp)
    pkb_denda: Optional[int] = None
    swdkllj_pokok: Optional[int] = None   # Sumbangan Wajib
    swdkllj_denda: Optional[int] = None
    total_tagihan: Optional[int] = None
    jatuh_tempo_pajak: Optional[str] = None   # "DD-MM-YYYY"
    jatuh_tempo_stnk: Optional[str] = None
    status_pajak: Optional[str] = None        # "Lunas" / "Belum Lunas"

    # Kepemilikan
    nama_pemilik: Optional[str] = None
    alamat: Optional[str] = None

    # Meta
    sumber:   Optional[str] = None
    catatan:  Optional[str] = None
    kabkota:  Optional[str] = None   # Kab/kota asal (dari suffix pattern, diisi crawler)
    no_rangka: Optional[str] = None  # Nomor rangka (dipakai Bali)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class BaseSamsatAdapter(ABC):
    region_code: str
    region_name: str
    needs_nik: bool = False

    @abstractmethod
    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        """Fetch vehicle info from the region's Samsat system."""
        ...

    def _empty(self, plate: str, error: str) -> VehicleInfo:
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.errors.append(error)
        return v
