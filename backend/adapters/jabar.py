"""
Adapter: Jawa Barat (Sambara)
Source: https://bapenda.jabarprov.go.id/sambara/
API: JSON endpoint — plate only, no NIK required
"""
import re
from typing import Optional

import httpx

from .base import BaseSamsatAdapter, VehicleInfo

# Sambara public API endpoint (Bapenda Jabar)
API_URL = "https://bapenda.jabarprov.go.id/sambara/api/pkb/kendaraan"
WEB_URL = "https://bapenda.jabarprov.go.id/sambara/"

HEADERS = {
    "User-Agent": "Sambara/4.0.1 (Android)",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-app-version": "4.0.1",
}


class JabarAdapter(BaseSamsatAdapter):
    region_code = "jabar"
    region_name = "Jawa Barat"
    needs_nik = False

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        plate_clean = plate.upper().replace(" ", "").replace("-", "")

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                # POST JSON
                payload = {"nopol": plate_clean}
                resp = await client.post(API_URL, json=payload, headers=HEADERS)

                if resp.status_code == 404:
                    return self._empty(plate, "Kendaraan tidak ditemukan di database Jawa Barat")
                resp.raise_for_status()

                data = resp.json()
                return self._parse(plate, data)

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses Sambara Jabar. Coba lagi.")
        except httpx.HTTPStatusError as e:
            # Fallback: web scraping
            return await self._fetch_web(plate, plate_clean)
        except Exception as e:
            return self._empty(plate, f"Error: {str(e)}")

    async def _fetch_web(self, plate: str, plate_clean: str) -> VehicleInfo:
        """Fallback web scraping jika API tidak tersedia."""
        from bs4 import BeautifulSoup

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                r = await client.get(WEB_URL, headers={
                    "User-Agent": "Mozilla/5.0 (Android 13; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0"
                })
                soup = BeautifulSoup(r.text, "html.parser")
                token_tag = soup.find("input", {"name": "_token"})
                token = token_tag.get("value", "") if token_tag else ""

                resp = await client.post(WEB_URL, data={
                    "_token": token,
                    "nopol": plate_clean,
                }, headers={"Referer": WEB_URL})

                return self._parse_html(plate, resp.text)
        except Exception as e:
            return self._empty(plate, f"Gagal mengakses Sambara: {str(e)}")

    def _parse(self, plate: str, data: dict) -> VehicleInfo:
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = WEB_URL

        # Sambara API response structure (may vary by version)
        kendaraan = data.get("kendaraan") or data.get("data", {})
        pajak = data.get("pajak") or data.get("tagihan", {})

        if not kendaraan and not pajak:
            # Maybe flat structure
            kendaraan = data
            pajak = data

        v.merk = kendaraan.get("merk") or kendaraan.get("merek")
        v.model = kendaraan.get("model") or kendaraan.get("tipe")
        v.tipe = kendaraan.get("tipe_kendaraan")
        v.warna = kendaraan.get("warna")
        v.tahun = _to_int(kendaraan.get("tahun"))
        v.jenis = kendaraan.get("jenis")
        v.bahan_bakar = kendaraan.get("bahan_bakar")
        v.cc = str(kendaraan.get("cc", "")) or None

        v.nama_pemilik = kendaraan.get("nama_pemilik") or kendaraan.get("nama")
        v.alamat = kendaraan.get("alamat")

        v.pkb_pokok = _to_int(pajak.get("pkb_pokok") or pajak.get("pkb"))
        v.pkb_denda = _to_int(pajak.get("pkb_denda") or pajak.get("denda_pkb"))
        v.swdkllj_pokok = _to_int(pajak.get("swdkllj_pokok") or pajak.get("swdkllj"))
        v.swdkllj_denda = _to_int(pajak.get("swdkllj_denda"))
        v.total_tagihan = _to_int(pajak.get("total_tagihan") or pajak.get("total"))
        v.jatuh_tempo_pajak = pajak.get("jatuh_tempo") or pajak.get("tgl_pajak")
        v.jatuh_tempo_stnk = pajak.get("jatuh_tempo_stnk") or pajak.get("tgl_stnk")
        v.status_pajak = pajak.get("status_bayar") or pajak.get("status")

        if not any([v.merk, v.total_tagihan]):
            v.errors.append("Data tidak ditemukan. Pastikan nomor polisi benar.")

        return v

    def _parse_html(self, plate: str, html: str) -> VehicleInfo:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)
        v.sumber = WEB_URL

        rows = {}
        for row in soup.select("table tr, .info-row"):
            cells = row.find_all(["td", "th", "span", "div"])
            if len(cells) >= 2:
                rows[cells[0].get_text(strip=True).lower()] = cells[1].get_text(strip=True)

        if not rows:
            v.errors.append("Data tidak tersedia dari Sambara Jawa Barat")
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
        v.nama_pemilik = get("nama")
        v.pkb_pokok = _parse_rupiah(get("pkb"))
        v.total_tagihan = _parse_rupiah(get("total", "jumlah"))
        v.jatuh_tempo_pajak = get("jatuh tempo", "pajak")
        v.jatuh_tempo_stnk = get("stnk")
        return v


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).replace(".", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_rupiah(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None
