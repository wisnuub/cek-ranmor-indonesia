"""
Adapter: Banten
Source: https://bapenda.bantenprov.go.id/esamsat/
Requires: Nomor Polisi + NIK
"""
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseSamsatAdapter, VehicleInfo

BASE_URL = "https://bapenda.bantenprov.go.id/esamsat/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": BASE_URL,
}


class BantenAdapter(BaseSamsatAdapter):
    region_code = "banten"
    region_name = "Banten"
    needs_nik = True

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        if not nik:
            v = self._empty(plate, "NIK diperlukan untuk cek kendaraan Banten")
            v.catatan = "Masukkan NIK (16 digit) pemilik kendaraan"
            return v

        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                r = await client.get(BASE_URL, headers=HEADERS)
                soup = BeautifulSoup(r.text, "html.parser")
                token_tag = soup.find("input", {"name": re.compile(r"token|csrf", re.I)})
                token = token_tag.get("value", "") if token_tag else ""

                payload = {
                    "_token": token,
                    "nopol": plate_clean,
                    "nik": nik.strip(),
                    "submit": "Cek",
                }
                resp = await client.post(BASE_URL, data=payload, headers=HEADERS)
                resp.raise_for_status()
                return self._parse(plate, resp.text)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses e-Samsat Banten")
        except Exception as e:
            return self._empty(plate, f"Error: {str(e)}")

    def _parse(self, plate: str, html: str) -> VehicleInfo:
        soup = BeautifulSoup(html, "html.parser")
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_URL

        rows: dict[str, str] = {}
        for tr in soup.select("table tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True).lower().rstrip(":")
                rows[k] = tds[1].get_text(strip=True)

        if not rows:
            v.errors.append("Data tidak ditemukan di e-Samsat Banten")
            return v

        def get(*keys):
            for k in keys:
                for rk, rv in rows.items():
                    if k in rk:
                        return rv
            return None

        v.merk = get("merk")
        v.model = get("model", "tipe")
        v.warna = get("warna")
        v.tahun = _to_int(get("tahun"))
        v.nama_pemilik = get("nama")
        v.pkb_pokok = _parse_rp(get("pkb"))
        v.total_tagihan = _parse_rp(get("total"))
        v.jatuh_tempo_pajak = get("jatuh tempo")
        v.jatuh_tempo_stnk = get("stnk")
        return v


def _to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"\d{4}", s)
    return int(m.group()) if m else None


def _parse_rp(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    d = re.sub(r"[^\d]", "", s)
    return int(d) if d else None
