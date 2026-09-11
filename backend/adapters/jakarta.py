"""
Adapter: DKI Jakarta
Source: https://soarest3.jakarta.go.id/soa/gov.dki.pkb/

Otentikasi:
  Pakai Google ID token dari app "Cek Ranmor DKI" via ADB.
  Jalankan: python backend/jakarta_refresh_token.py
  File session: backend/jakarta_session.json

  Token Google ID berlaku 1 jam. Script refresh mengambil token baru
  dari SharedPreferences app Android via ADB.

  Jika token expired, adapter tandai needs_relogin=True.

API:
  GET /soa/gov.dki.pkb/f2501/{PREFIX}/{NOPA}/{NOPH}/NONIK/LIGHT/
  Header: Authorization: Bearer {id_token}
          User-Agent: myAndroidCk2017

  Maintenance: Senin-Kamis 22:00-00:00, Jumat 19:00-00:00, Sabtu 13:00-16:00 WIB
"""
import json
import re
import time
import base64
import logging
from pathlib import Path
from typing import Optional

import httpx

from .base import BaseSamsatAdapter, VehicleInfo

log = logging.getLogger("adapter.jakarta")

SESSION_FILE  = Path(__file__).parent.parent / "jakarta_session.json"
SOAREST_BASE  = "https://soarest3.jakarta.go.id"
SOAREST_SOA   = f"{SOAREST_BASE}/soa/gov.dki.pkb"
TOKEN_URL     = f"{SOAREST_SOA}/token"
LOOKUP_URL    = f"{SOAREST_SOA}/f2501"
SAMSAT_WEB    = "https://samsat-pkb2.jakarta.go.id/"

# ── Session cache ─────────────────────────────────────────────────────────────

_session_cache: dict | None = None
_session_mtime: float = 0.0


def _load_session() -> dict | None:
    """Load session dari file, re-load jika file berubah."""
    global _session_cache, _session_mtime
    if not SESSION_FILE.exists():
        return None
    mtime = SESSION_FILE.stat().st_mtime
    if _session_cache is None or mtime != _session_mtime:
        try:
            _session_cache = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            _session_mtime = mtime
            log.info("Jakarta session loaded from %s", SESSION_FILE)
        except Exception as e:
            log.error("Gagal load jakarta_session.json: %s", e)
            return None
    return _session_cache


def _get_id_token(session: dict) -> Optional[str]:
    """Ambil Google ID token dari session."""
    return session.get("id_token") or session.get("jwt_token")


def _token_is_valid(token: str) -> bool:
    """Cek apakah JWT token masih berlaku (belum exp)."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return False
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(padded))
        exp = payload.get("exp", 0)
        return time.time() < exp - 30  # 30-detik buffer
    except Exception:
        return False


# ── Plate parsing ─────────────────────────────────────────────────────────────

def _split_plate(plate: str) -> tuple[str, str, str] | None:
    """
    B5651EP  → ("B", "5651", "EP")
    B 5651 EP → same
    """
    plate = plate.upper().replace(" ", "").replace("-", "")
    m = re.match(r'^([A-Z]{1,2})(\d+)([A-Z]*)$', plate)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


# ── Response parsers ──────────────────────────────────────────────────────────

def _parse_rupiah(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None


def _parse_year(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"\d{4}", str(s))
    return int(m.group()) if m else None


def _parse_response(plate: str, data: dict, v: VehicleInfo) -> VehicleInfo:
    """
    Parse JSON response dari soarest3 f2501.

    Field names dari API (sesuai hasil reverse-engineering):
      Merek, Model, Tipe, Tahun Buat, Warna, BBM,
      Masa Pajak, Masa STNK,
      Pajak Kendaraan, Denda Pajak, SWDKLLJ, Denda SWDKLLJ, Total,
      Nama, Alamat, Kab. Kota, No. Rangka, No. Mesin, No. BPKB,
      Nilai Jual, PNBP Cetak STNK, PNBP Plat (TNKB),
      NOPOL, Plat, CC Kendaraan, Kendaraan ke-, Keterangan
    """
    def get(*keys):
        for k in keys:
            if k in data and data[k] not in (None, "", "-", "LAIN-LAIN"):
                return str(data[k])
            # case-insensitive fallback
            kl = k.lower()
            for dk, dv in data.items():
                if dk.lower() == kl and dv not in (None, "", "-", "LAIN-LAIN"):
                    return str(dv)
        return None

    v.merk         = get("Merek", "merk", "brand")
    v.model        = get("Model", "model")
    v.tipe         = get("Tipe", "tipe")
    v.warna        = get("Warna", "warna", "color")
    v.jenis        = get("CC Kendaraan", "jenis_kendaraan", "jenis")
    v.bahan_bakar  = get("BBM", "bahan_bakar", "fuel")
    v.cc           = get("CC Kendaraan", "cc")
    v.nama_pemilik = get("Nama", "nama_pemilik", "nama")
    v.alamat       = get("Alamat", "alamat")
    v.kabkota      = get("Kab. Kota", "kabkota")
    v.no_rangka    = get("No. Rangka", "no_rangka")

    v.tahun = _parse_year(get("Tahun Buat", "tahun", "year"))

    # BBM: normalise bahan bakar
    bbm_raw = data.get("BBM", "")
    if bbm_raw and bbm_raw not in ("LAIN-LAIN", "-", ""):
        v.bahan_bakar = bbm_raw

    # Pajak fields
    v.pkb_pokok     = _parse_rupiah(get("Pajak Kendaraan", "pkb_pokok", "pkb"))
    v.pkb_denda     = _parse_rupiah(get("Denda Pajak", "pkb_denda"))
    v.swdkllj_pokok = _parse_rupiah(get("SWDKLLJ", "swdkllj_pokok", "swdkllj"))
    v.swdkllj_denda = _parse_rupiah(get("Denda SWDKLLJ", "swdkllj_denda"))
    v.total_tagihan = _parse_rupiah(get("Total", "total_tagihan"))
    v.jatuh_tempo_pajak = get("Masa Pajak", "jatuh_tempo_pajak", "jatuh_tempo")
    v.jatuh_tempo_stnk  = get("Masa STNK", "jatuh_tempo_stnk", "berlaku_stnk")

    if v.total_tagihan and v.total_tagihan > 0:
        v.status_pajak = "Belum Lunas"
    elif v.pkb_pokok is not None:
        v.status_pajak = "Lunas"

    v.sumber = LOOKUP_URL
    return v


# ── Main adapter ──────────────────────────────────────────────────────────────

class JakartaAdapter(BaseSamsatAdapter):
    region_code   = "jakarta"
    region_name   = "DKI Jakarta"
    needs_nik     = False
    needs_captcha = False

    async def fetch(self, plate: str, nik: Optional[str] = None) -> VehicleInfo:
        v = VehicleInfo(plate=plate, region=self.region_code, region_name=self.region_name)

        session = _load_session()
        if not session:
            v.errors.append(
                "Session Jakarta belum ada. "
                "Jalankan: python backend/jakarta_refresh_token.py"
            )
            v.catatan = f"Cek manual di: {SAMSAT_WEB}"
            return v

        id_token = _get_id_token(session)
        if not id_token:
            v.errors.append(
                "Token Google tidak ditemukan di session. "
                "Jalankan: python backend/jakarta_refresh_token.py"
            )
            return v

        if not _token_is_valid(id_token):
            v.errors.append(
                "Token Google expired (berlaku 1 jam). "
                "Jalankan: python backend/jakarta_refresh_token.py"
            )
            v.needs_relogin = True
            return v

        parsed = _split_plate(plate)
        if not parsed:
            v.errors.append(f"Format plat tidak valid: {plate}")
            return v

        prefix, num_part, suf_part = parsed

        # Susun URL: /f2501/{PREFIX}/{NOPA}/{NOPH}/NONIK/LIGHT/
        url = f"{LOOKUP_URL}/{prefix}/{num_part}/{suf_part}/NONIK/LIGHT/"

        user_agent = session.get("user_agent", "myAndroidCk2017")
        req_headers = {
            "User-Agent":    user_agent,
            "Accept":        "application/json",
            "Authorization": f"Bearer {id_token}",
        }

        try:
            async with httpx.AsyncClient(
                timeout=12.0,
                headers=req_headers,
                follow_redirects=True,
            ) as client:
                # Step 1: Authenticate session (wajib sebelum /f2501)
                # POST /token dengan Bearer header di session yang sama
                # Tanpa ini, /f2501 return "Terjadi kesalahan, tutup aplikasi..."
                tok_resp = await client.post(TOKEN_URL, json={})
                log.debug("soarest3 POST /token → %d", tok_resp.status_code)

                if tok_resp.status_code in (401, 403):
                    v.errors.append(
                        "Token Jakarta ditolak saat /token (401/403). "
                        "Jalankan: python backend/jakarta_refresh_token.py"
                    )
                    v.needs_relogin = True
                    return v

                # Step 2: Lookup plat
                resp = await client.get(url)

                log.debug("soarest3 GET %s → %d", url, resp.status_code)

                if resp.status_code in (401, 403):
                    v.errors.append(
                        "Token Jakarta ditolak (401/403). "
                        "Jalankan: python backend/jakarta_refresh_token.py"
                    )
                    v.needs_relogin = True
                    return v

                if resp.status_code == 404:
                    return v  # plat tidak terdaftar

                resp.raise_for_status()

                try:
                    data = resp.json()
                except Exception:
                    return v

                status = str(data.get("status", "0"))
                if status == "-1":
                    # Server maintenance — tandai error tapi bukan relogin
                    ket = data.get("Keterangan", "Server maintenance")
                    log.warning("Jakarta maintenance: %s", ket)
                    v.errors.append(f"Server maintenance: {ket}")
                    return v
                if status != "1":
                    # status=0 = tidak ditemukan (normal saat crawl)
                    log.debug("Jakarta %s: tidak ditemukan (ket=%s)",
                              plate, data.get("Keterangan", ""))
                    return v

                return _parse_response(plate, data, v)

        except httpx.TimeoutException:
            v.errors.append(f"Timeout soarest3. Cek manual: {SAMSAT_WEB}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                v.errors.append("Rate limited (429) — kurangi kecepatan crawl")
            else:
                v.errors.append(f"HTTP {e.response.status_code} dari soarest3")
        except httpx.RemoteProtocolError:
            # F5 WAF disconnect = rate limited, treat as empty (tidak ditemukan)
            log.debug("Jakarta rate-limited (RemoteProtocolError) on %s", plate)
        except Exception as e:
            log.debug("Jakarta fetch error: %s", e)
            v.errors.append(f"Error: {e}")

        return v
