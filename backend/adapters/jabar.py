"""
Adapter: Jawa Barat (Sambara / Bapenda Jabar)
Source: https://bapenda.jabarprov.go.id/infopkb/

API flow (reverse-engineered dari Sambara APK):
  POST https://bapenda.jabarprov.go.id/sambara/api/pkb/kendaraan
  Headers: User-Agent: Sambara/5.x, x-app-version: 5.x
  Body:    {"nopol": "D5651EP"}

Catatan:
  API Sambara kadang unreachable dari luar jaringan Jabar / dikurangi aksesnya.
  Adapter ini mencoba beberapa endpoint dan fallback ke scraping web infopkb.
"""
import re
from typing import Optional

import httpx

from .base import BaseSamsatAdapter, VehicleInfo

WEB_URL  = "https://bapenda.jabarprov.go.id/infopkb/"
API_URLS = [
    "https://bapenda.jabarprov.go.id/sambara/api/pkb/kendaraan",
    "https://bapenda.jabarprov.go.id/sambara/api/v2/pkb/kendaraan",
]

_HEADERS_API = {
    "User-Agent":    "Sambara/5.0.0 (Android 13; SDK 33)",
    "Accept":        "application/json",
    "Content-Type":  "application/json",
    "x-app-version": "5.0.0",
}

_HEADERS_WEB = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer":         WEB_URL,
}


class JabarAdapter(BaseSamsatAdapter):
    region_code = "jabar"
    region_name = "Jawa Barat"
    needs_nik   = False

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        # Coba API endpoint satu per satu
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for url in API_URLS:
                try:
                    resp = await client.post(url, json={"nopol": plate_clean},
                                             headers=_HEADERS_API)
                    if resp.status_code == 200:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct:
                            data = resp.json()
                            v = self._parse_json(plate, data)
                            if v.merk or v.model:
                                return v
                    elif resp.status_code == 404:
                        return self._empty(plate, "Kendaraan tidak ditemukan di database Jawa Barat")
                except (httpx.TimeoutException, httpx.ConnectError):
                    continue   # coba endpoint berikutnya
                except Exception:
                    continue

        # Fallback: scrape halaman infopkb
        try:
            return await self._fetch_web(plate, plate_clean)
        except httpx.TimeoutException:
            pass
        except Exception:
            pass

        return self._empty(
            plate,
            f"API Sambara Jawa Barat tidak tersedia saat ini. "
            f"Cek manual: {WEB_URL}"
        )

    async def _fetch_web(self, plate: str, plate_clean: str) -> VehicleInfo:
        """Scraping halaman infopkb sebagai fallback."""
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # GET dulu untuk ambil token CSRF jika ada
            r = await client.get(WEB_URL, headers=_HEADERS_WEB)
            soup = BeautifulSoup(r.text, "html.parser")
            token_tag = soup.find("input", {"name": "_token"})
            token = token_tag.get("value", "") if token_tag else ""

            resp = await client.post(WEB_URL, data={
                "_token": token,
                "nopol":  plate_clean,
            }, headers=_HEADERS_WEB)
            return self._parse_html(plate, resp.text)

    def _parse_json(self, plate: str, data: dict) -> VehicleInfo:
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = WEB_URL

        # Sambara returns {"kendaraan":{...}, "pajak":{...}} or flat
        kend = data.get("kendaraan") or data.get("data") or data
        pajak = data.get("pajak") or data.get("tagihan") or data

        if not isinstance(kend, dict):
            kend = {}
        if not isinstance(pajak, dict):
            pajak = {}

        v.merk         = kend.get("merk") or kend.get("merek")
        v.model        = kend.get("model") or kend.get("tipe")
        v.tipe         = kend.get("tipe_kendaraan")
        v.warna        = kend.get("warna")
        v.tahun        = _to_int(kend.get("tahun"))
        v.jenis        = kend.get("jenis")
        v.bahan_bakar  = kend.get("bahan_bakar")
        v.cc           = str(kend.get("cc", "") or "").strip() or None
        v.nama_pemilik = kend.get("nama_pemilik") or kend.get("nama")
        v.alamat       = kend.get("alamat")

        v.pkb_pokok     = _to_int(pajak.get("pkb_pokok") or pajak.get("pkb"))
        v.pkb_denda     = _to_int(pajak.get("pkb_denda") or pajak.get("denda_pkb"))
        v.swdkllj_pokok = _to_int(pajak.get("swdkllj_pokok") or pajak.get("swdkllj"))
        v.swdkllj_denda = _to_int(pajak.get("swdkllj_denda"))
        v.total_tagihan = _to_int(pajak.get("total_tagihan") or pajak.get("total"))
        v.jatuh_tempo_pajak = pajak.get("jatuh_tempo") or pajak.get("tgl_pajak")
        v.jatuh_tempo_stnk  = pajak.get("jatuh_tempo_stnk") or pajak.get("tgl_stnk")
        v.status_pajak      = pajak.get("status_bayar") or pajak.get("status")

        if not v.merk and not v.total_tagihan:
            v.errors.append("Data kendaraan tidak ditemukan di database Jawa Barat")
        return v

    def _parse_html(self, plate: str, html: str) -> VehicleInfo:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = WEB_URL

        rows: dict[str, str] = {}
        for row in soup.select("table tr, .info-row, dl dt"):
            if row.name == "dt":
                dd = row.find_next_sibling("dd")
                if dd:
                    rows[row.get_text(strip=True).lower()] = dd.get_text(strip=True)
            else:
                cells = row.find_all(["td", "th", "span", "div"])
                if len(cells) >= 2:
                    rows[cells[0].get_text(strip=True).lower()] = cells[1].get_text(strip=True)

        if not rows:
            v.errors.append(
                f"Data tidak tersedia dari Sambara Jawa Barat. "
                f"Cek manual: {WEB_URL}"
            )
            return v

        def get(*keys):
            for k in keys:
                for rk, rv in rows.items():
                    if k in rk:
                        return rv
            return None

        v.merk          = get("merk", "merek")
        v.model         = get("model", "tipe")
        v.warna         = get("warna")
        v.tahun         = _to_int(get("tahun"))
        v.nama_pemilik  = get("nama")
        v.pkb_pokok     = _parse_rupiah(get("pkb"))
        v.total_tagihan = _parse_rupiah(get("total", "jumlah"))
        v.jatuh_tempo_pajak = get("jatuh tempo", "pajak")
        v.jatuh_tempo_stnk  = get("stnk")

        if not v.merk:
            v.errors.append(
                f"Data tidak ditemukan. Cek manual di: {WEB_URL}"
            )
        return v


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).replace(".", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_rupiah(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None
