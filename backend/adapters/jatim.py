"""
Adapter: Jawa Timur
Source: https://info.dipendajatim.go.id/esamsat/
Requires: Nomor Polisi + NIK
"""
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseSamsatAdapter, VehicleInfo

BASE_URL = "https://info.dipendajatim.go.id/esamsat/"
QUERY_URL = "https://info.dipendajatim.go.id/esamsat/cek_kendaraan_bermotor_pub.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": BASE_URL,
    "Origin": "https://info.dipendajatim.go.id",
}


class JatimAdapter(BaseSamsatAdapter):
    region_code = "jatim"
    region_name = "Jawa Timur"
    needs_nik = True

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        if not nik:
            v = self._empty(plate, "NIK diperlukan untuk cek kendaraan Jawa Timur")
            v.catatan = "Masukkan NIK (16 digit) pemilik kendaraan"
            return v

        plate_clean = plate.upper().replace(" ", "").replace("-", "")
        # Split plate: e.g. "L1234XYZ" → nopol_dep="L" nopol_mid="1234" nopol_bel="XYZ"
        m = re.match(r"^([A-Z]{1,2})(\d{1,4})([A-Z]{1,3})$", plate_clean)
        if not m:
            return self._empty(plate, f"Format plat '{plate}' tidak valid untuk Jawa Timur")

        nopol_dep, nopol_mid, nopol_bel = m.groups()

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                payload = {
                    "nopol_dep": nopol_dep,
                    "nopol_mid": nopol_mid,
                    "nopol_bel": nopol_bel,
                    "nik": nik.strip(),
                    "submit": "Cek",
                }
                resp = await client.post(QUERY_URL, data=payload, headers=HEADERS)
                resp.raise_for_status()
                return self._parse(plate, resp.text)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses e-Samsat Jawa Timur")
        except httpx.HTTPStatusError as e:
            return self._empty(plate, f"HTTP {e.response.status_code} dari e-Samsat Jatim")
        except Exception as e:
            return self._empty(plate, f"Error: {str(e)}")

    def _parse(self, plate: str, html: str) -> VehicleInfo:
        soup = BeautifulSoup(html, "html.parser")
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_URL

        # Check error
        err = soup.find(class_=re.compile(r"error|alert-danger|pesan", re.I))
        if err:
            v.errors.append(err.get_text(strip=True)[:200])
            return v

        rows: dict[str, str] = {}
        for tr in soup.select("table.table tr, table tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True).lower().rstrip(":")
                val = tds[1].get_text(strip=True)
                rows[k] = val

        if not rows:
            v.errors.append("Data tidak ditemukan. Pastikan nomor polisi dan NIK benar.")
            return v

        def get(*keys):
            for k in keys:
                for rk, rv in rows.items():
                    if k in rk:
                        return rv
            return None

        v.merk = get("merk", "merek")
        v.model = get("model", "tipe kendaraan")
        v.tipe = get("tipe")
        v.warna = get("warna")
        v.tahun = _to_int(get("tahun"))
        v.jenis = get("jenis")
        v.bahan_bakar = get("bahan bakar")
        v.cc = get("cc", "isi silinder")
        v.nama_pemilik = get("nama")
        v.alamat = get("alamat")

        v.pkb_pokok = _parse_rp(get("pkb pokok"))
        v.pkb_denda = _parse_rp(get("denda pkb", "pkb denda"))
        v.swdkllj_pokok = _parse_rp(get("swdkllj pokok", "swdkllj"))
        v.swdkllj_denda = _parse_rp(get("swdkllj denda", "denda swdkllj"))
        v.total_tagihan = _parse_rp(get("total tagihan", "total bayar", "total"))
        v.jatuh_tempo_pajak = get("jatuh tempo pajak", "masa berlaku pajak")
        v.jatuh_tempo_stnk = get("berlaku s/d", "masa berlaku stnk", "stnk")

        if v.total_tagihan and v.total_tagihan > 0:
            v.status_pajak = "Belum Lunas"
        elif v.pkb_pokok:
            v.status_pajak = "Lunas"

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
