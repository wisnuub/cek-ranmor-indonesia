"""
Adapter: Jawa Tengah (Samsat Jateng — "New Sakpole" API)
Endpoint: POST https://samsat.jatengprov.go.id/info/kendaraan/api/api_req_info_kbm
(also used by the app for api_req_info_pajak with the same token formula)

Token algorithm reverse-engineered from the "New Sakpole" APK
(com.jatengprov.bapenda.newsakpole, libapp.so ARM64) via blutter (Dart AOT
decompiler), and verified byte-for-byte against a real device's logcat
(Decoded Key / Hash1 / Encrypt Key / MD5 / Final Token all matched).

Utility.generateTokenVehicle @ 0x75457c:
  key    = "BAPENDA JATENG"
  hash1  = SHA512(key + input).hexdigest()
  hash2  = SHA512(input + key).hexdigest()
  mid    = SHA512(hash1 + key + hash2).hexdigest()
  fin    = SHA1(SHA1(MD5(mid).hexdigest()).hexdigest()).hexdigest()

Where `input` is built as (app_provider.dart, kbmCheck @ 0x779720):
  input = na + nb + SALT + nc
SALT is a literal string baked into the app and used AS-IS —
it is itself base64 text, but the app does NOT decode it before
splicing it into `input`:
  SALT = "Zmxld3Rocm91Z2hvdXRwYXJ0aWN1bGFydm93ZWxzZW5kc2hpcnRhbXNsZWVwaG9sZWI="

This SALT is the key difference from the older "Sakpole" app (which used
plain `na + nb + nc` with no salt) — the old formula was rejected by the
server after the app update, which is why this adapter needed re-deriving.

Request body (VehicleRequest.toJson @ 0x754050):
  na    = plate prefix letters  (e.g. "H")
  nb    = plate digits          (e.g. "1234")
  nc    = plate suffix letters  (e.g. "GH")
  noka  = chassis number        (empty for public lookup)
  key   = "TkVXIFNBS1BPTEU="   (field_47 in the kbm flow, app_provider.dart:8166)
  token = generateTokenVehicle(na + nb + SALT + nc)

Second endpoint — api_req_info_pajak (tax nominal breakdown):
Endpoint: POST https://samsat.jatengprov.go.id/info/kendaraan/api/api_req_info_pajak
Reached from checkVehicleTax<Y0> @ 0x77c744 (app_provider.dart), the handler
behind the app's separate "Cek Pajak" screen (vehicle_tax_check_controller.dart),
which — unlike the plate-only "Cek Kendaraan" screen — also collects a chassis
number (noka) field before submitting.

Verified via disassembly that checkVehicleTax builds its token input
IDENTICALLY to kbmCheck (same interpolation: na + nb + SALT + nc @ 0x77c81c-
0x77c84c) — `noka` is NOT part of the token input, it is only a separate
VehicleRequest JSON field (field_13). So the same _generate_token_vehicle()
is reused; only the payload's `noka` field and the target URL differ.

Without a non-empty `noka`, this endpoint replies
{"Status":"6001","Msg":"Silahkan update aplikasi"} — a misleading generic
error that is actually just "required field missing", not a real version
check (confirmed: no app-version header exists anywhere in ApiConfig).

Response schema (VehicleTaxCheckResponse, response/vehicle_tax_check_response.dart,
fromJson @ 0x6ce78c / mirrored copyWith @ 0x77cf78) adds tax-nominal fields
on top of the same identity fields as api_req_info_kbm:
  total_pkb_prov, total_pkb_denda_prov, total_pkb_opsen, total_pkb_denda_opsen,
  total_pkb_pokok, total_pkb_denda, jumlah_pkb,
  total_jr_pokok, total_jr_denda, jumlah_jr, pnbp, total,
  tgl_jatuh_tempo, status_pajak, sts_pajak, th_tgk,
  rincian: [{masa_akhir_berlaku_pajak, jatuh_tempo_pembayaran, lama_tunggakan,
             pokok_pkb, pokok_pkb_opsen, pokok_jr, denda_pkb, denda_pkb_opsen,
             denda_jr, pnbp, total, terlambat, no_skpd, ket_pajak}, ...]
"""

import hashlib
import re
from typing import Optional

import httpx

from .base import BaseSamsatAdapter, VehicleInfo

# ── Constants ────────────────────────────────────────────────────────────────

API_BASE       = "https://samsat.jatengprov.go.id"
API_ENDPOINT   = f"{API_BASE}/info/kendaraan/api/api_req_info_kbm"
PAJAK_ENDPOINT = f"{API_BASE}/info/kendaraan/api/api_req_info_pajak"

# Hardcoded in the app for this endpoint (app_provider.dart line 8162-8166)
APP_KEY = "TkVXIFNBS1BPTEU="

# Literal salt spliced (raw, NOT base64-decoded) between nb and nc when
# building the token input — see Utility::generateTokenVehicle callers
# in app_provider.dart (kbmCheck @ 0x779720, checkVehicleTax @ 0x77c85c)
TOKEN_SALT = "Zmxld3Rocm91Z2hvdXRwYXJ0aWN1bGFydm93ZWxzZW5kc2hpcnRhbXNsZWVwaG9sZWI="

# Matches typical Dio + OkHttp user-agent from the Flutter app
_HEADERS = {
    "User-Agent":   "okhttp/4.9.3",
    "Content-Type": "application/json; charset=utf-8",
    "Accept":       "application/json",
}


# ── Token generation ─────────────────────────────────────────────────────────

def _generate_token_vehicle(token_input: str) -> str:
    """
    Python port of Utility::generateTokenVehicle (New Sakpole ARM64, @ 0x75457c).

    token_input = na + nb + TOKEN_SALT + nc
    """
    key   = "BAPENDA JATENG"
    h1    = hashlib.sha512((key + token_input).encode()).hexdigest()
    h2    = hashlib.sha512((token_input + key).encode()).hexdigest()
    mid   = hashlib.sha512((h1 + key + h2).encode()).hexdigest()
    md5_  = hashlib.md5(mid.encode()).hexdigest()
    sha1a = hashlib.sha1(md5_.encode()).hexdigest()
    return  hashlib.sha1(sha1a.encode()).hexdigest()


# ── Plate splitting ──────────────────────────────────────────────────────────

_PLATE_RE = re.compile(r'^([A-Z]{1,3})\s*(\d{1,4})\s*([A-Z]{0,3})$')


def _split_plate(plate: str) -> tuple[str | None, str | None, str | None]:
    """
    Split a Jateng-format plate into (na, nb, nc).

    "H 1234 GH" → ("H", "1234", "GH")
    "AA 9876 B"  → ("AA", "9876", "B")
    """
    clean = plate.upper().replace("-", "").strip()
    m = _PLATE_RE.match(clean)
    if not m:
        return None, None, None
    return m.group(1), m.group(2), m.group(3)


# ── Adapter ──────────────────────────────────────────────────────────────────

class JatengAdapter(BaseSamsatAdapter):
    region_code = "jateng"
    region_name = "Jawa Tengah"
    needs_nik   = False

    async def fetch(self, plate: str, nik: Optional[str] = None,
                    noka: Optional[str] = None) -> VehicleInfo:
        """
        noka: nomor rangka (chassis number) — opsional. Jika diisi, adapter
        memanggil api_req_info_pajak (nominal pajak rinci per tahun) alih-alih
        api_req_info_kbm (info dasar kendaraan tanpa nominal pajak).
        """
        na, nb, nc = _split_plate(plate)
        if na is None:
            return self._empty(plate, "Format plat tidak valid untuk wilayah Jateng")

        token_input = na + nb + TOKEN_SALT + nc   # e.g. "H1234<salt>GH"
        token = _generate_token_vehicle(token_input)
        noka = (noka or "").strip()

        payload: dict = {
            "na":    na,
            "nb":    nb,
            "nc":    nc,
            "noka":  noka,
            "req":   "",
            "key":   APP_KEY,
            "token": token,
        }

        endpoint = PAJAK_ENDPOINT if noka else API_ENDPOINT
        parse    = self._parse_pajak if noka else self._parse

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    endpoint,
                    json=payload,
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                return parse(plate, resp.json())

        except httpx.TimeoutException:
            return self._empty(plate, "Timeout saat mengakses API Samsat Jawa Tengah")
        except httpx.HTTPStatusError as e:
            return self._empty(
                plate,
                f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except Exception as e:
            return self._empty(plate, f"Error: {e}")

    def _parse(self, plate: str, data: dict) -> VehicleInfo:
        v = VehicleInfo(
            plate=plate,
            region=self.region_code,
            region_name=self.region_name,
        )
        v.sumber = API_BASE

        # API response structure (confirmed from live probes):
        #   Status "000"   → success, data is flat in root
        #   Status "99999" → vehicle not found
        #   Status "498"   → invalid token
        raw_status = str(data.get("Status") or data.get("status") or "")

        if raw_status != "000":
            msg = (
                data.get("Msg")
                or data.get("msg")
                or data.get("Message")
                or data.get("message")
                or f"Status API: {raw_status}"
            )
            if raw_status == "99999":
                msg = "Data kendaraan tidak ditemukan"
            v.errors.append(str(msg))
            return v

        # Data is flat in the root object (no nested "data" key)
        body = data

        def g(*keys: str) -> Optional[str]:
            for k in keys:
                val = body.get(k)
                if val not in (None, "", "-", 0):
                    return str(val).strip()
            return None

        def gi(*keys: str) -> Optional[int]:
            """Get integer field directly (already numeric in response)."""
            for k in keys:
                val = body.get(k)
                if val not in (None, "", "-") and val != 0:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
            return None

        # Kendaraan
        v.merk         = g("merek")
        v.tipe         = g("tipe")           # e.g. "F1C02N46L0 A/T"
        v.model        = g("tipe", "merek")  # best label for display
        v.jenis        = g("model")          # e.g. "SPM/SEPEDA MOTOR"
        v.warna        = g("WarnaKB", "warna_tnkb")
        v.tahun        = _to_int(g("thn_buat"))
        v.bahan_bakar  = g("bbm")
        v.cc           = g("cylinder")

        # Pajak — Samsat Jateng uses "jr" for SWDKLLJ since 2025 reform
        # "opsen" = opsen PKB (kabupaten/kota 66% share), separate line since Jan 2025
        v.pkb_pokok     = gi("pkb_pokok")
        v.pkb_denda     = gi("pkb_denda")
        # total_pkb_pokok = pkb_pokok + pkb_pokok_opsen (combined for display)
        v.swdkllj_pokok = gi("jr_pokok", "total_jr_pokok")
        v.swdkllj_denda = gi("jr_denda", "total_jr_denda")
        v.total_tagihan = gi("total")

        # Tanggal
        v.jatuh_tempo_pajak = g("tgl_jatuh_tempo")   # "13-03-2027"
        v.jatuh_tempo_stnk  = g("tgl_stnk")          # "13-03-2028"

        # Status
        v.status_pajak = g("status_pajak")            # "LUNAS" / "BELUM LUNAS"
        v.kabkota      = g("lokasi_samsat")            # "UNGARAN"

        return v

    def _parse_pajak(self, plate: str, data: dict) -> VehicleInfo:
        """
        Parse api_req_info_pajak response (VehicleTaxCheckResponse,
        response/vehicle_tax_check_response.dart @ 0x6ce78c). Same identity
        fields as api_req_info_kbm plus a detailed tax-nominal breakdown
        ("rincian" = per-tahun breakdown array — not surfaced individually,
        only the pre-aggregated totals below are mapped to VehicleInfo).
        """
        v = VehicleInfo(
            plate=plate,
            region=self.region_code,
            region_name=self.region_name,
        )
        v.sumber = API_BASE

        raw_status = str(data.get("Status") or data.get("status") or "")

        if raw_status != "000":
            msg = (
                data.get("Msg")
                or data.get("msg")
                or data.get("Message")
                or data.get("message")
                or f"Status API: {raw_status}"
            )
            if raw_status == "99999":
                msg = "Data kendaraan tidak ditemukan"
            elif raw_status == "6001":
                msg = "Nomor rangka tidak sesuai atau tidak lengkap"
            v.errors.append(str(msg))
            return v

        body = data

        def g(*keys: str) -> Optional[str]:
            for k in keys:
                val = body.get(k)
                if val not in (None, "", "-", 0):
                    return str(val).strip()
            return None

        def gi(*keys: str) -> Optional[int]:
            for k in keys:
                val = body.get(k)
                if val not in (None, "", "-") and val != 0:
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        pass
            return None

        # Kendaraan
        v.merk        = g("merek")
        v.tipe        = g("tipe")
        v.model       = g("tipe", "merek")
        v.jenis       = g("model")
        v.warna       = g("WarnaKB", "warna_tnkb")
        v.tahun       = _to_int(g("thn_buat"))
        v.bahan_bakar = g("bbm")
        v.cc          = g("cylinder")

        # Pajak — total_pkb_pokok/total_pkb_denda already include opsen PKB
        v.pkb_pokok     = gi("total_pkb_pokok")
        v.pkb_denda     = gi("total_pkb_denda")
        v.swdkllj_pokok = gi("total_jr_pokok")
        v.swdkllj_denda = gi("total_jr_denda")
        v.total_tagihan = gi("total")

        # Tanggal
        v.jatuh_tempo_pajak = g("tgl_jatuh_tempo")
        v.jatuh_tempo_stnk  = g("tgl_stnk")

        # Status
        v.status_pajak = g("status_pajak")
        v.kabkota      = g("lokasi_samsat")

        return v


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"\d{4}", s)
    return int(m.group()) if m else None


def _parse_rp(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None
