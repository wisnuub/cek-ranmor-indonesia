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
# Nomor 1-999 adalah plat khusus/dinas — plat sipil biasa minimal 4 digit (≥1000)
NUMBER_RANGES_GENERAL = {
    "mobil":   (1_000, 1_999),
    "motor":   (2_000, 6_999),
    "bus":     (7_000, 7_999),
    "barang":  (8_000, 8_999),
    "khusus":  (9_000, 9_999),
    "all":     (1_000, 9_999),
    # Default crawl range: skip nomor rendah (1-1499, jarang dipakai plat sipil)
    # dan skip bus/barang/khusus (7000+) — fokus mobil-atas + semua motor.
    "default": (1_500, 6_999),
}

# Khusus Polda Metro Jaya (plat B — Jakarta, Depok, Tangerang, Bekasi)
NUMBER_RANGES_B = {
    "mobil":   (1_000, 2_999),
    "motor":   (3_000, 6_999),
    "bus":     (7_000, 7_999),
    "barang":  (8_000, 8_999),
    "khusus":  (9_000, 9_999),
    "all":     (1_000, 9_999),
    "default": (1_500, 6_999),
}

def get_number_range(region: str, mode: str = "default") -> tuple[int, int]:
    """Ambil range angka berdasarkan region dan mode kendaraan."""
    ranges = NUMBER_RANGES_B if region == "jakarta" else NUMBER_RANGES_GENERAL
    return ranges.get(mode, ranges["default"])

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

# Jawa Tengah — MULTI-PREFIX: tiap kode wilayah (G/H/K/R) punya arti suffix
# BERBEDA, jadi tidak bisa digabung jadi satu dict datar seperti region lain.
# Sumber: detik.com/jateng (d-7017496), caroline.id, auto2000.co.id
JATENG_KABKOTA_BY_PREFIX: dict[str, dict[str, str]] = {
    "H": {  # Semarang & sekitarnya
        "A": "Kota Semarang", "F": "Kota Semarang", "G": "Kota Semarang", "H": "Kota Semarang",
        "P": "Kota Semarang", "Q": "Kota Semarang", "R": "Kota Semarang", "S": "Kota Semarang",
        "W": "Kota Semarang", "X": "Kota Semarang", "Y": "Kota Semarang", "Z": "Kota Semarang",
        "B": "Kota Salatiga", "K": "Kota Salatiga", "O": "Kota Salatiga", "T": "Kota Salatiga",
        "C": "Kab. Semarang", "I": "Kab. Semarang", "L": "Kab. Semarang", "V": "Kab. Semarang",
        "D": "Kab. Kendal",   "M": "Kab. Kendal",   "U": "Kab. Kendal",
        "E": "Kab. Demak",    "J": "Kab. Demak",    "N": "Kab. Demak",
    },
    "G": {  # Pekalongan & sekitarnya
        "A": "Kota Pekalongan", "H": "Kota Pekalongan", "S": "Kota Pekalongan",
        "B": "Kab. Pekalongan", "K": "Kab. Pekalongan", "O": "Kab. Pekalongan", "T": "Kab. Pekalongan",
        "C": "Kab. Batang",     "L": "Kab. Batang",     "V": "Kab. Batang",     "X": "Kab. Batang",
        "D": "Kab. Pemalang",   "I": "Kab. Pemalang",   "M": "Kab. Pemalang",   "W": "Kab. Pemalang",
        "E": "Kota Tegal",      "N": "Kota Tegal",      "Y": "Kota Tegal",
        "F": "Kab. Tegal",      "P": "Kab. Tegal",      "Q": "Kab. Tegal",      "Z": "Kab. Tegal",
        "G": "Kab. Brebes",     "J": "Kab. Brebes",     "R": "Kab. Brebes",     "U": "Kab. Brebes",
    },
    "K": {  # Pati & sekitarnya
        "A": "Kab. Pati",     "G": "Kab. Pati",     "H": "Kab. Pati",     "S": "Kab. Pati",     "U": "Kab. Pati",
        "B": "Kab. Kudus",    "K": "Kab. Kudus",    "O": "Kab. Kudus",    "R": "Kab. Kudus",    "T": "Kab. Kudus",
        "C": "Kab. Jepara",   "L": "Kab. Jepara",   "Q": "Kab. Jepara",   "V": "Kab. Jepara",
        "D": "Kab. Rembang",  "I": "Kab. Rembang",  "M": "Kab. Rembang",  "W": "Kab. Rembang",
        "E": "Kab. Blora",    "N": "Kab. Blora",    "X": "Kab. Blora",    "Y": "Kab. Blora",
        "F": "Kab. Grobogan", "J": "Kab. Grobogan", "P": "Kab. Grobogan", "Z": "Kab. Grobogan",
    },
    "R": {  # Banyumas & sekitarnya — hanya Kab. Banyumas terdokumentasi;
            # Cilacap/Purbalingga/Banjarnegara pakai kombinasi huruf lain (belum diketahui)
        "A": "Kab. Banyumas", "E": "Kab. Banyumas", "G": "Kab. Banyumas", "H": "Kab. Banyumas",
        "J": "Kab. Banyumas", "S": "Kab. Banyumas", "X": "Kab. Banyumas",
    },
}

# Gabungan semua kabkota per region (single-prefix regions)
KABKOTA_MAP: dict[str, dict[str, str]] = {
    "bali":    BALI_KABKOTA,
    "jakarta": JAKARTA_KABKOTA,
    "jabar":   JABAR_D_KABKOTA,
    # Jateng: lihat JATENG_KABKOTA_BY_PREFIX (multi-prefix, tidak datar)
    # DIY, dll — first letters belum terdokumentasi lengkap, pakai semua A-Z
}

# Prefix utama per region (dipakai untuk region single-prefix / tampilan info)
REGION_PREFIX: dict[str, str] = {
    "bali":    "DK",
    "jabar":   "D",
    "jateng":  "H",
    "diy":     "AB",
    "jakarta": "B",
}

# Region dengan LEBIH DARI SATU prefix plat (dicrawl semua secara berurutan)
REGION_PREFIXES: dict[str, list[str]] = {
    "jateng": ["H", "G", "K", "R"],  # H (Semarang) duluan — paling padat & sudah terverifikasi
}


def get_region_prefixes(region: str) -> list[str]:
    """Daftar semua prefix plat yang perlu di-crawl untuk satu region."""
    if region in REGION_PREFIXES:
        return REGION_PREFIXES[region]
    p = REGION_PREFIX.get(region)
    return [p] if p else []


# ────────────────────────────────────────────────────────────────────────────
# SMART SUFFIX GENERATOR
# Urutan: known first-letters + seri A-Z → 2-letter → 3-letter
# ────────────────────────────────────────────────────────────────────────────

import itertools
import string

# Huruf yang dipakai (tanpa I dan O — bisa dikecualikan tapi Bali pakai I)
ALL_LETTERS = list(string.ascii_uppercase)
SAFE_LETTERS = [c for c in ALL_LETTERS if c not in ("O",)]  # Bali pakai I, jadi hanya skip O


def _kabkota_for(region: str, prefix: str | None = None) -> dict[str, str]:
    """Resolve the kab/kota-by-suffix-first-letter dict for a region (+ plate prefix)."""
    if region == "jateng" and prefix:
        return JATENG_KABKOTA_BY_PREFIX.get(prefix.upper(), {})
    return KABKOTA_MAP.get(region, {})


def generate_smart_suffixes(region: str, prefix: str | None = None) -> list[str]:
    """
    Generate suffix dalam urutan yang paling efisien.

    CATATAN PENTING: plat Indonesia SELALU minimal 2 huruf suffix.
    Tidak ada plat seperti D5000A — yang benar D5000AA atau lebih.
    Jadi kita SKIP semua single-letter suffix.

    Urutan:
    1. Two-letter: known_first + A-Z   (e.g. AA, AB, ..., ZZ)
    2. Three-letter: known_first + A-Z + A-Z
    3. Brute-force: unknown first letters (2-letter)
    4. Brute-force: unknown first letters (3-letter)

    prefix: kode plat spesifik (relevan untuk region multi-prefix seperti
    jateng — G/H/K/R punya makna suffix yang berbeda-beda).
    """
    kabkota = _kabkota_for(region, prefix)
    known_firsts = list(kabkota.keys())
    unknown_firsts = [c for c in ALL_LETTERS if c not in known_firsts]

    result = []
    seen = set()

    def add(s: str):
        if s not in seen:
            seen.add(s)
            result.append(s)

    # 1. Two-letter: known_first + A-Z
    for fl in known_firsts:
        for sl in ALL_LETTERS:
            add(fl + sl)

    # 2. Three-letter: known_first + A-Z + A-Z
    for fl in known_firsts:
        for sl in ALL_LETTERS:
            for tl in ALL_LETTERS:
                add(fl + sl + tl)

    # 3. Brute-force: unknown first letters (2-letter)
    for fl in unknown_firsts:
        for sl in ALL_LETTERS:
            add(fl + sl)

    # 4. Brute-force: unknown first letters (3-letter)
    for fl in unknown_firsts:
        for sl in ALL_LETTERS:
            for tl in ALL_LETTERS:
                add(fl + sl + tl)

    return result


def get_kabkota_from_suffix(region: str, suffix: str, prefix: str | None = None) -> str:
    """Identifikasi kab/kota dari suffix pertama (+ plate prefix untuk region multi-prefix)."""
    if not suffix:
        return "Unknown"
    kabkota = _kabkota_for(region, prefix)
    return kabkota.get(suffix[0].upper(), "Unknown")


# ── Backwards-compat aliases (dipakai di main.py) ─────────────────────────────
KNOWN_SUFFIXES      = KABKOTA_MAP   # {region: {first_letter: kab/kota}}
REGION_PRIMARY_PREFIX = REGION_PREFIX  # {region: prefix}
