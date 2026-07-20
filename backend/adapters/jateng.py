"""
Adapter: Jawa Tengah (Sakpole / e-Samsat)
Source: https://sakpole.dppad.jatengprov.go.id/
Plate only (no NIK required for info dasar)
"""
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .base import BaseSamsatAdapter, VehicleInfo

BASE_URL = "https://sakpole.dppad.jatengprov.go.id/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Android 13; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "id-ID,id;q=0.9",
    "Referer": BASE_URL,
}


class JatengAdapter(BaseSamsatAdapter):
    region_code = "jateng"
    region_name = "Jawa Tengah"
    needs_nik = False

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                # Get main page for CSRF
                r = await client.get(BASE_URL, headers=HEADERS)
                soup = BeautifulSoup(r.text, "html.parser")
                token_tag = soup.find("input", {"name": re.compile(r"token|_token|csrf", re.I)})
                token = token_tag.get("value", "") if token_tag else ""

                payload = {
                    "_token": token,
                    "nopol": plate_clean,
                }
                if nik:
                    payload["nik"] = nik.strip()

                resp = await client.post(BASE_URL, data=payload, headers=HEADERS)
                resp.raise_for_status()
                return self._parse(plate, resp.text)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses Sakpole Jawa Tengah")
        except Exception as e:
            return self._empty(plate, f"Error: {str(e)}")

    def _parse(self, plate: str, html: str) -> VehicleInfo:
        soup = BeautifulSoup(html, "html.parser")
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = BASE_URL

        rows: dict[str, str] = {}
        for tr in soup.select("tr, .info-item"):
            tds = tr.find_all(["td", "th", "li", "span"])
            if len(tds) >= 2:
                k = tds[0].get_text(strip=True).lower().rstrip(":")
                rows[k] = tds[1].get_text(strip=True)

        if not rows:
            # Try definition list
            for dt in soup.select("dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    rows[dt.get_text(strip=True).lower()] = dd.get_text(strip=True)

        if not rows:
            v.errors.append("Data tidak ditemukan. Sakpole Jawa Tengah mungkin sedang gangguan.")
            return v

        def get(*keys):
            for k in keys:
                for rk, rv in rows.items():
                    if k in rk:
                        return rv
            return None

        v.merk = get("merk", "merek")
        v.model = get("model", "tipe")
        v.warna = get("warna")
        v.tahun = _to_int(get("tahun"))
        v.jenis = get("jenis")
        v.nama_pemilik = get("nama")
        v.pkb_pokok = _parse_rp(get("pkb"))
        v.swdkllj_pokok = _parse_rp(get("swdkllj"))
        v.total_tagihan = _parse_rp(get("total", "jumlah"))
        v.jatuh_tempo_pajak = get("jatuh tempo", "pajak")
        v.jatuh_tempo_stnk = get("stnk", "berlaku")
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
