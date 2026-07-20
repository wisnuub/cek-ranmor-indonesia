"""
Adapter: Bali
Source: https://portal.bpdbali.id/infosamsat/
Verifikasi: Nomor Polisi + Warna Plat + 5 digit terakhir Nomor Rangka
"""
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseSamsatAdapter, VehicleInfo

BASE_URL  = "https://portal.bpdbali.id/infosamsat/"
HEADERS   = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":     "text/html,application/xhtml+xml",
    "Referer":    BASE_URL,
}

# Warna plat: 01=Putih (pribadi), 02=Kuning (umum), 03=Merah (dinas)
PLATE_COLOR_DEFAULT = "01"


class BaliAdapter(BaseSamsatAdapter):
    region_code = "bali"
    region_name = "Bali"
    needs_nik   = False

    async def fetch(self, plate: str, nik: Optional[str] = None,
                    vin_last5: Optional[str] = None,
                    plate_color: str = PLATE_COLOR_DEFAULT) -> VehicleInfo:
        """
        plate       : mis. DK3456FCR
        nik         : tidak dipakai oleh Samsat Bali
        vin_last5   : 5 digit terakhir nomor rangka (optional — tanpa ini hasil kosong)
        plate_color : "01" Putih, "02" Kuning, "03" Merah
        """
        plate_clean = plate.upper().replace(" ", "").replace("-", "")
        # Prefix DK sudah fix, rest = bagian setelah DK
        prefix = "DK"
        police_field = plate_clean[len(prefix):] if plate_clean.startswith(prefix) else plate_clean

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
                # GET untuk ambil session + token
                r = await client.get(BASE_URL, headers=HEADERS)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")

                form     = soup.find("form")
                tok_inp  = soup.find("input", {"name": "t:formdata"})
                tok_val  = tok_inp.get("value", "") if tok_inp else ""
                action   = form.get("action", "/infosamsat/index.form") if form else "/infosamsat/index.form"
                post_url = f"https://portal.bpdbali.id{action}"

                payload = {
                    "t:formdata":       tok_val,
                    "textfield":        prefix,
                    "policeField":      police_field,
                    "policeNumberType": plate_color,
                    "vinField":         (vin_last5 or "").strip(),
                    "process":          "PROSES",
                }
                resp = await client.post(post_url, data=payload, headers={
                    **HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                resp.raise_for_status()
                return self._parse(plate, resp.text, vin_last5)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses Samsat Bali")
        except Exception as e:
            return self._empty(plate, f"Error Samsat Bali: {str(e)}")

    def _parse(self, plate: str, html: str, vin_last5: Optional[str]) -> VehicleInfo:
        soup = BeautifulSoup(html, "html.parser")
        v    = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_URL

        # Ambil semua baris tabel
        rows: dict[str, str] = {}
        for tr in soup.select("table tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True).lower().rstrip(":")
                rows[k] = tds[1].get_text(strip=True)

        # Coba dl / definition list
        if not rows:
            for dt in soup.select("dl dt, .label"):
                dd = dt.find_next_sibling(["dd", ".value"])
                if dd:
                    rows[dt.get_text(strip=True).lower()] = dd.get_text(strip=True)

        if not rows:
            hint = "" if vin_last5 else " (tanpa nomor rangka hasilnya kosong)"
            v.errors.append(f"Data tidak ditemukan di Samsat Bali{hint}")
            return v

        def get(*keys):
            for k in keys:
                for rk, rv in rows.items():
                    if k in rk:
                        return rv
            return None

        v.merk           = get("merk")
        v.model          = get("model", "tipe kendaraan", "tipe")
        v.warna          = get("warna")
        v.tahun          = _to_int(get("tahun"))
        v.jenis          = get("jenis")
        v.bahan_bakar    = get("bahan bakar", "bbm")
        v.cc             = get("cc", "isi silinder")
        v.nama_pemilik   = get("nama")
        v.alamat         = get("alamat")
        v.pkb_pokok      = _parse_rp(get("pkb pokok", "pkb"))
        v.pkb_denda      = _parse_rp(get("denda pkb", "pkb denda"))
        v.swdkllj_pokok  = _parse_rp(get("swdkllj pokok", "swdkllj"))
        v.swdkllj_denda  = _parse_rp(get("denda swdkllj", "swdkllj denda"))
        v.total_tagihan  = _parse_rp(get("total", "jumlah tagihan"))
        v.jatuh_tempo_pajak = get("jatuh tempo pajak", "jatuh tempo", "tgl pajak")
        v.jatuh_tempo_stnk  = get("berlaku stnk", "stnk")

        if v.total_tagihan and v.total_tagihan > 0:
            v.status_pajak = "Belum Lunas"
        elif v.pkb_pokok is not None:
            v.status_pajak = "Lunas"

        return v


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).replace(".", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_rp(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    d = re.sub(r"[^\d]", "", s)
    return int(d) if d else None
