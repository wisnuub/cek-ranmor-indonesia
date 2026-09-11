"""
Adapter: DI Yogyakarta
Source: https://samsatsleman.jogjaprov.go.id/cek/pajak
API: AJAX JSON — plate only (no NIK, no CAPTCHA)
Coverage: Semua kab/kota DIY (Sleman, Bantul, Gunungkidul, Kulon Progo, Kota YK)
"""
import re
from typing import Optional

import httpx

from .base import BaseSamsatAdapter, VehicleInfo

BASE_WEB = "https://samsatsleman.jogjaprov.go.id/cek/pajak"
API_URL  = "https://samsatsleman.jogjaprov.go.id/cek/pages/getpajak"

HEADERS = {
    "User-Agent":        "Mozilla/5.0 (Android 13; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0",
    "Accept":            "application/json, */*; q=0.01",
    "X-Requested-With":  "XMLHttpRequest",
    "Referer":           BASE_WEB,
    "Content-Type":      "application/x-www-form-urlencoded; charset=UTF-8",
}


class DIYAdapter(BaseSamsatAdapter):
    region_code = "diy"
    region_name = "DI Yogyakarta"
    needs_nik   = False

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        # AB1234GA → prefix=AB, nomor=1234, suffix=GA
        # Strip leading letters (prefix = AB), then digits, then trailing letters (suffix)
        m = re.match(r'^([A-Z]+)(\d+)([A-Z]+)$', plate_clean)
        if not m:
            return self._empty(plate, f"Format plat tidak valid: {plate}")

        nomer  = m.group(2)   # angka, e.g. "1234"
        suffix = m.group(3)   # huruf belakang, e.g. "GA"

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
                                         verify=False) as client:
                resp = await client.post(
                    API_URL,
                    data={"nomer": nomer, "kode_belakang": suffix},
                    headers=HEADERS,
                )
                resp.raise_for_status()
                return self._parse(plate, resp.json())

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses Samsat DIY. Coba lagi.")
        except Exception as e:
            return self._empty(plate, f"Error: {str(e)}")

    def _parse(self, plate: str, data: dict) -> VehicleInfo:
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_WEB

        if data.get("status") != "success" or not data.get("data"):
            v.errors.append("Kendaraan tidak ditemukan di database Samsat DIY Yogyakarta")
            return v

        d = data["data"]

        v.merk  = d.get("nmmerekkb", "").strip() or None
        v.model = d.get("nmmodelkb", "").strip() or None
        v.tahun = _to_int(d.get("tahunkb"))

        v.pkb_pokok      = _to_int(d.get("pkbpok"))
        v.pkb_denda      = _to_int(d.get("pkbden"))
        v.swdkllj_pokok  = _to_int(d.get("swdpok"))
        v.swdkllj_denda  = _to_int(d.get("swdden"))
        v.total_tagihan  = _to_int(d.get("pkbswd"))   # pkbswd = grand total PKB+SWD
        v.jatuh_tempo_pajak = d.get("tgakhirpkb") or None

        if v.total_tagihan == 0 and v.pkb_pokok:
            v.status_pajak = "Lunas"
        elif v.total_tagihan and v.total_tagihan > 0:
            v.status_pajak = "Belum Lunas"

        return v


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).replace(".", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None
