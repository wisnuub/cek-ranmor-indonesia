"""
Adapter: Bali
Source: https://bpd.baliprov.go.id/esamsat/ / https://infosamsat.baliprov.go.id/
Plate only (no NIK for basic info)
"""
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseSamsatAdapter, VehicleInfo

BASE_URL = "https://infosamsat.baliprov.go.id/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Referer": BASE_URL,
}


class BaliAdapter(BaseSamsatAdapter):
    region_code = "bali"
    region_name = "Bali"
    needs_nik = False

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                r = await client.get(BASE_URL, headers=HEADERS)
                soup = BeautifulSoup(r.text, "html.parser")
                token_tag = soup.find("input", {"name": re.compile(r"token|csrf", re.I)})
                token = token_tag.get("value", "") if token_tag else ""

                payload = {"nopol": plate_clean, "_token": token}
                if nik:
                    payload["nik"] = nik.strip()

                resp = await client.post(BASE_URL, data=payload, headers=HEADERS)
                resp.raise_for_status()

                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    return self._parse_json(plate, resp.json())
                return self._parse_html(plate, resp.text)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses Samsat Bali")
        except Exception as e:
            return self._empty(plate, f"Error: {str(e)}")

    def _parse_json(self, plate: str, data: dict) -> VehicleInfo:
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_URL
        v.merk = data.get("merk")
        v.model = data.get("model") or data.get("tipe")
        v.warna = data.get("warna")
        v.tahun = _to_int(data.get("tahun"))
        v.nama_pemilik = data.get("nama") or data.get("nama_pemilik")
        v.pkb_pokok = _to_int(data.get("pkb") or data.get("pkb_pokok"))
        v.total_tagihan = _to_int(data.get("total") or data.get("total_tagihan"))
        v.jatuh_tempo_pajak = data.get("jatuh_tempo") or data.get("tgl_jth_tempo")
        v.jatuh_tempo_stnk = data.get("tgl_stnk")
        v.status_pajak = data.get("status")
        return v

    def _parse_html(self, plate: str, html: str) -> VehicleInfo:
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
            v.errors.append("Data tidak ditemukan di Samsat Bali")
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
