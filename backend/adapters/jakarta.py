"""
Adapter: DKI Jakarta
Source: https://samsat-pkb2.jakarta.go.id/
Requires: Nomor Polisi + NIK
"""
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseSamsatAdapter, VehicleInfo

BASE_URL = "https://samsat-pkb2.jakarta.go.id/"
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer":         BASE_URL,
}
# Form fields: nopa = angka (e.g."5651"), noph = huruf suffix (e.g."EP"), flag="2"
# NIK wajib, dan Samsat Jakarta menggunakan CAPTCHA — tidak bisa otomatisasi tanpa solver


class JakartaAdapter(BaseSamsatAdapter):
    region_code = "jakarta"
    region_name = "DKI Jakarta"
    needs_nik = True

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        if not nik:
            v = self._empty(plate, "NIK diperlukan untuk cek kendaraan DKI Jakarta")
            v.catatan = "Masukkan NIK (16 digit) pemilik kendaraan"
            return v

        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                # Step 1: get CSRF token
                r = await client.get(BASE_URL, headers=HEADERS)
                r.raise_for_status()

                soup = BeautifulSoup(r.text, "html.parser")
                token_tag = soup.find("input", {"name": "_token"})
                if not token_tag:
                    return self._empty(plate, "Gagal mendapatkan token dari Samsat Jakarta")
                token = token_tag.get("value", "")

                # Step 2: POST query
                # Form fields: nopa=angka, noph=huruf suffix, flag=2
                # Contoh: B5651EP → nopa="5651", noph="EP"
                num_part = re.sub(r"[^0-9]", "", plate_clean[1:])   # strip prefix B, ambil angka
                suf_part = re.sub(r"[^A-Z]", "", plate_clean)       # semua huruf = suffix termasuk prefix? No:
                # plate_clean = "B5651EP" → prefix=B, angka=5651, suffix=EP
                suf_part = re.sub(r"^[A-Z]+\d+", "", plate_clean)   # hapus prefix+angka, sisa = suffix
                payload = {
                    "nopa": num_part,
                    "noph": suf_part,
                    "nik":  nik.strip(),
                    "flag": "2",
                }
                resp = await client.post(BASE_URL, data=payload, headers=HEADERS)
                resp.raise_for_status()

                return self._parse(plate, resp.text)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses Samsat Jakarta. Coba lagi.")
        except httpx.HTTPStatusError as e:
            return self._empty(plate, f"HTTP {e.response.status_code} dari Samsat Jakarta")
        except Exception as e:
            return self._empty(plate, f"Error tidak terduga: {str(e)}")

    def _parse(self, plate: str, html: str) -> VehicleInfo:
        soup = BeautifulSoup(html, "html.parser")
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_URL

        # Check for error message
        err = soup.find(class_=re.compile(r"alert|error|warning", re.I))
        if err:
            v.errors.append(err.get_text(strip=True))
            return v

        # Parse table rows — Jakarta uses a dl/dt/dd or table layout
        rows = {}
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).lower()
                val = cells[1].get_text(strip=True)
                rows[key] = val

        if not rows:
            # Try dl layout
            for dt in soup.select("dl dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    rows[dt.get_text(strip=True).lower()] = dd.get_text(strip=True)

        if not rows:
            v.errors.append("Data tidak ditemukan. Pastikan nomor polisi dan NIK benar.")
            return v

        def get(*keys):
            for k in keys:
                for rk, rv in rows.items():
                    if k.lower() in rk:
                        return rv
            return None

        v.merk = get("merk")
        v.model = get("model", "type")
        v.warna = get("warna")
        v.tahun = _to_int(get("tahun"))
        v.jenis = get("jenis")
        v.bahan_bakar = get("bahan bakar", "bbm")
        v.nama_pemilik = get("nama")
        v.alamat = get("alamat")

        raw_pkb = get("pkb pokok", "pkb")
        v.pkb_pokok = _parse_rupiah(raw_pkb)
        v.pkb_denda = _parse_rupiah(get("pkb denda", "denda pkb"))
        v.swdkllj_pokok = _parse_rupiah(get("swdkllj pokok", "swdkllj"))
        v.swdkllj_denda = _parse_rupiah(get("swdkllj denda"))
        v.total_tagihan = _parse_rupiah(get("total", "jumlah"))
        v.jatuh_tempo_pajak = get("jatuh tempo", "tgl jatuh")
        v.jatuh_tempo_stnk = get("stnk", "berlaku stnk")

        if v.total_tagihan is not None and v.total_tagihan > 0:
            v.status_pajak = "Belum Lunas"
        elif v.pkb_pokok is not None:
            v.status_pajak = "Lunas"

        return v


def _to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"\d{4}", s)
    return int(m.group()) if m else None


def _parse_rupiah(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None
