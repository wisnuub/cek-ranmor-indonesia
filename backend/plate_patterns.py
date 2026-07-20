"""
Indonesian plate number patterns — data dari artikel resmi & komunitas otomotif.

Struktur plat: PREFIX + ANGKA + SUFFIX
  - PREFIX  : kode provinsi (B, D, DK, dll.)
  - ANGKA   : range menentukan jenis kendaraan
  - SUFFIX  : 1-3 huruf, huruf pertama = kab/kota, sisanya = seri urut

Sumber:
  - Peraturan Kepolisian No. 7 Tahun 2021
  - IDN Times Bali, Daihatsu.co.id, Auto2000, Kompas.com
"""

# ────────────────────────────────────────────────────────────────────────────
# RANGE ANGKA → JENIS KENDARAAN
# ────────────────────────────────────────────────────────────────────────────

# Umum (luar Polda Metro Jaya)
NUMBER_RANGES_GENERAL = {
    "mobil":  (1,    1_999),
    "motor":  (2_000, 6_999),
    "bus":    (7_000, 7_999),
    "barang": (8_000, 8_999),
    "khusus": (9_000, 9_999),
    "all":    (1,    9_999),
}

# Khusus Polda Metro Jaya (plat B — Jakarta, Depok, Tangerang, Bekasi)
NUMBER_RANGES_B = {
    "mobil":  (1,    2_999),
    "motor":  (3_000, 6_999),
    "bus":    (7_000, 7_999),
    "barang": (8_000, 8_999),
    "khusus": (9_000, 9_999),
    "all":    (1,    9_999),
}

def get_number_range(region: str, mode: str = "all") -> tuple[int, int]:
    """Ambil range angka berdasarkan region dan mode kendaraan."""
    ranges = NUMBER_RANGES_B if region == "jakarta" else NUMBER_RANGES_GENERAL
    return ranges.get(mode, ranges["all"])

def guess_jenis(region: str, number: int) -> str:
    """Estimasi jenis kendaraan dari angka plat."""
    ranges = NUMBER_RANGES_B if region == "jakarta" else NUMBER_RANGES_GENERAL
    if ranges["mobil"][0]  <= number <= ranges["mobil"][1]:  return "Mobil Penumpang"
    if ranges["motor"][0]  <= number <= ranges["motor"][1]:  return "Sepeda Motor"
    if ranges["bus"][0]    <= number <= ranges["bus"][1]:    return "Bus"
    if ranges["barang"][0] <= number <= ranges["barang"][1]: return "Kendaraan Barang"
    return "Kendaraan Khusus"


# ────────────────────────────────────────────────────────────────────────────
# SUFFIX — HURUF PERTAMA PER KABUPATEN/KOTA
# Huruf pertama suffix = kode kab/kota
# Huruf selanjutnya   = seri urut (A-Z, AA-ZZ, AAA-ZZZ)
# ────────────────────────────────────────────────────────────────────────────

# Bali (DK)
# Sumber: IDN Times Bali, Traveloka, Daihatsu.co.id
BALI_KABKOTA: dict[str, str] = {
    "A": "Kota Denpasar",    "B": "Kota Denpasar",
    "C": "Kota Denpasar",    "D": "Kota Denpasar",
    "E": "Kota Denpasar",    "I": "Kota Denpasar",
    "Q": "Kota Denpasar",    "X": "Kota Denpasar",
    "F": "Kab. Badung",      "J": "Kab. Badung",      "O": "Kab. Badung",
    "W": "Kab. Jembrana",    "Z": "Kab. Jembrana",
    "K": "Kab. Gianyar",     "L": "Kab. Gianyar",
    "G": "Kab. Tabanan",     "H": "Kab. Tabanan",
    "U": "Kab. Buleleng",    "V": "Kab. Buleleng",
    "S": "Kab. Karangasem",  "T": "Kab. Karangasem",
    "M": "Kab. Klungkung",   "N": "Kab. Klungkung",
    "P": "Kab. Bangli",      "R": "Kab. Bangli",
    "Y": "Kota Denpasar",    # seri lanjutan
}

# Jakarta (B) — huruf pertama suffix = kota/kab
# Sumber: Daihatsu.co.id, Auto2000, Auksi.co.id
JAKARTA_KABKOTA: dict[str, str] = {
    "U": "Jakarta Utara",
    "B": "Jakarta Barat",
    "P": "Jakarta Pusat",
    "S": "Jakarta Selatan",
    "T": "Jakarta Timur",
    "E": "Kota Depok",          "Z": "Kota Depok",
    "C": "Kota Tangerang",      "V": "Kota Tangerang",
    "N": "Kab. Tangerang",      "G": "Kab. Tangerang",
    "K": "Kota Bekasi",
    "F": "Kab. Bekasi",
    "W": "Kota Tangerang Selatan",
}

# Jawa Barat (D — Bandung & sekitarnya)
# Sumber: Daihatsu.co.id, Kumparan
JABAR_D_KABKOTA: dict[str, str] = {
    # Kota Bandung (paling banyak)
    "A": "Kota Bandung", "B": "Kota Bandung", "C": "Kota Bandung",
    "D": "Kota Bandung", "E": "Kota Bandung", "F": "Kota Bandung",
    "G": "Kota Bandung", "H": "Kota Bandung", "I": "Kota Bandung",
    "J": "Kota Bandung", "K": "Kota Bandung", "L": "Kota Bandung",
    "M": "Kota Bandung", "N": "Kota Bandung", "O": "Kota Bandung",
    "P": "Kota Bandung", "R": "Kota Bandung",
    # Kota Cimahi
    "S": "Kota Cimahi",  "T": "Kota Cimahi",
    # Kab. Bandung Barat
    "U": "Kab. Bandung Barat", "W": "Kab. Bandung Barat", "X": "Kab. Bandung Barat",
    # Kab. Bandung
    "V": "Kab. Bandung", "Y": "Kab. Bandung", "Z": "Kab. Bandung",
}

# Gabungan semua kabkota per region
KABKOTA_MAP: dict[str, dict[str, str]] = {
    "bali":    BALI_KABKOTA,
    "jakarta": JAKARTA_KABKOTA,
    "jabar":   JABAR_D_KABKOTA,
    # Jateng, DIY, dll — first letters belum terdokumentasi lengkap, pakai semua A-Z
}

# Prefix utama per region
REGION_PREFIX: dict[str, str] = {
    "bali":    "DK",
    "jabar":   "D",
    "jateng":  "H",
    "diy":     "AB",
    "jakarta": "B",
}


# ────────────────────────────────────────────────────────────────────────────
# SMART SUFFIX GENERATOR
# Urutan: known first-letters + seri A-Z → 2-letter → 3-letter
# ────────────────────────────────────────────────────────────────────────────

import itertools
import string

# Huruf yang dipakai (tanpa I dan O — bisa dikecualikan tapi Bali pakai I)
ALL_LETTERS = list(string.ascii_uppercase)
SAFE_LETTERS = [c for c in ALL_LETTERS if c not in ("O",)]  # Bali pakai I, jadi hanya skip O


def generate_smart_suffixes(region: str) -> list[str]:
    """
    Generate suffix dalam urutan yang paling efisien:
    1. Known single-letter first codes (per kab/kota)
    2. Two-letter: [first_letter][A-Z]
    3. Three-letter: [first_letter][A-Z][A-Z]
    4. Brute-force sisa (huruf yang tidak ada di map)
    """
    kabkota = KABKOTA_MAP.get(region, {})
    known_firsts = list(kabkota.keys())  # e.g. Bali: A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R,S,T,U,V,W,X,Y,Z
    unknown_firsts = [c for c in ALL_LETTERS if c not in known_firsts]

    result = []
    seen = set()

    def add(s: str):
        if s not in seen:
            seen.add(s)
            result.append(s)

    # 1. Single letter (semua known first letters)
    for fl in known_firsts:
        add(fl)

    # 2. Two-letter: known_first + A-Z
    for fl in known_firsts:
        for sl in ALL_LETTERS:
            add(fl + sl)

    # 3. Three-letter: known_first + A-Z + A-Z
    for fl in known_firsts:
        for sl in ALL_LETTERS:
            for tl in ALL_LETTERS:
                add(fl + sl + tl)

    # 4. Brute-force: unknown first letters (single)
    for fl in unknown_firsts:
        add(fl)

    # 5. Brute-force: unknown first letters (2-letter)
    for fl in unknown_firsts:
        for sl in ALL_LETTERS:
            add(fl + sl)

    # 6. Brute-force: unknown first letters (3-letter)
    for fl in unknown_firsts:
        for sl in ALL_LETTERS:
            for tl in ALL_LETTERS:
                add(fl + sl + tl)

    return result


def get_kabkota_from_suffix(region: str, suffix: str) -> str:
    """Identifikasi kab/kota dari suffix pertama."""
    if not suffix:
        return "Unknown"
    kabkota = KABKOTA_MAP.get(region, {})
    return kabkota.get(suffix[0].upper(), "Unknown")


# ── Backwards-compat aliases (dipakai di main.py) ─────────────────────────────
KNOWN_SUFFIXES      = KABKOTA_MAP   # {region: {first_letter: kab/kota}}
REGION_PRIMARY_PREFIX = REGION_PREFIX  # {region: prefix}
