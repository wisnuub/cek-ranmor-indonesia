"""
Normalisasi field `jenis` ke 5 kategori baku (JENIS_LIST di frontend):
"Sepeda Motor", "Mobil Penumpang", "Mobil Bus", "Mobil Barang", "Kendaraan Khusus".

Kenapa perlu ini: tiap daerah punya format `jenis` mentah yang beda-beda dari
API Samsat masing-masing (mis. Jateng pakai kode "SPM/SEPEDA MOTOR",
"MPNP/MINIBUS", "MBRG/LIGHT TRUCK"; DIY malah sama sekali tidak mengembalikan
field jenis — selalu NULL). Filter pencarian di crud.py butuh nilai yang
konsisten di semua region supaya "Sepeda Motor" / "Mobil ..." bisa match.

Untuk region yang jenis-nya NULL (DIY), fallback ke klasifikasi berbasis
merk (& model untuk merk yang jual motor SEKALIGUS mobil, mis. Honda/Suzuki)
karena tidak ada info lain yang bisa dipakai.
"""

import re

SEPEDA_MOTOR   = "Sepeda Motor"
MOBIL_PENUMPANG = "Mobil Penumpang"
MOBIL_BUS      = "Mobil Bus"
MOBIL_BARANG   = "Mobil Barang"
KENDARAAN_KHUSUS = "Kendaraan Khusus"


# ── 1. Normalisasi kode mentah yang SUDAH ADA di field jenis (mis. Jateng) ──

_RAW_PREFIX_MAP = {
    "SPM":  SEPEDA_MOTOR,
    "MPNP": MOBIL_PENUMPANG,
    "MNP":  MOBIL_PENUMPANG,
    "MBUS": MOBIL_BUS,
    "MBRG": MOBIL_BARANG,
}


def normalize_raw_jenis(raw: str | None) -> str | None:
    """Normalisasi jenis yang formatnya 'KODE/DESKRIPSI', mis. 'SPM/SEPEDA MOTOR'."""
    if not raw:
        return None
    raw = raw.strip().upper()

    prefix = raw.split("/")[0].strip()
    if prefix in _RAW_PREFIX_MAP:
        return _RAW_PREFIX_MAP[prefix]

    if "RODA TIGA" in raw:
        # Motor roda tiga (mis. Viar) vs mobil roda tiga (bemo/tossa) — keduanya
        # kendaraan niche, kelompokkan sebagai Kendaraan Khusus kecuali eksplisit "SPM".
        return SEPEDA_MOTOR if raw.startswith("SPM") else KENDARAAN_KHUSUS

    if "SEPEDA MOTOR" in raw or "MOTOR" in raw:
        return SEPEDA_MOTOR
    if "MINIBUS" in raw:
        return MOBIL_PENUMPANG
    if "MIKROBUS" in raw or re.search(r"\bBUS\b", raw):
        return MOBIL_BUS
    if any(k in raw for k in ("TRUCK", "TRUK", "PICK UP", "PICKUP", "BAK", "TRONTON", "TRACTOR", "BOX", "DUMP")):
        return MOBIL_BARANG
    if any(k in raw for k in ("SEDAN", "JEEP", "MOBIL")):
        return MOBIL_PENUMPANG
    return None


# ── 2. Klasifikasi fallback berbasis merk untuk region tanpa field jenis ────

# Merk yang HANYA jual sepeda motor/skuter di Indonesia (mayoritas >99% row).
MOTOR_BRANDS = {
    "YAMAHA", "KAWASAKI", "VESPA", "VIAR", "SANEX", "DAIHEIYO", "TOSSA",
    "PIAGGIO", "TVS", "TVS KING", "BAJAJ", "JIALING", "KYMCO", "MINERVA",
    "LONCIN", "LONCINI", "WANGGUAN", "WANGGUAN HOKAIDO", "KASEA", "BINTER",
    "KANZEN", "JINCHENG", "JINCHENG CITI", "QINGQI", "ZEALSUN", "BEIJING",
    "YING XIANG", "MILLENNIUM", "MILLENIUM", "TURBO", "DAYANG", "JIANSHE",
    "VIVA", "MOCIN", "LIFAN", "KAISAR", "BENELLI", "GARUDA", "DKW",
    "HARLEY DAVIDSON", "DAST", "SUMO", "MAX", "UWINFLY", "ROYAL ENFIELD",
    "JETWIN", "MAHATOR", "BSA", "BALADA", "GESITS", "SMOOT ELEKTRIK",
    "QESTAR", "QE STAR", "CHUNLAN", "HOKAIDO", "ZONGSHEN", "YAZUKI",
    "YASUKI", "YADEA", "KTM", "APP KTM", "GAZA", "XIN DONGLI",
    "XIN DONGLI (XDL", "SM SPORT", "MONSTRAC", "WINS", "SUNDIRO",
    "LAMBRETA", "LAMBRETA".upper(), "HTM", "BOSOWA-HYOSUNG", "AYS", "ALVA",
    "SUPER STAR", "SUPERSTAR", "KEEWAY", "DUCATI", "VOLTA", "NOZOMI",
    "HONLEI", "EXOTIC", "WMOTO", "UNITED", "SELIS", "PACIFIC", "GAZGAS",
    "ECGO", "DIABLO", "SYM", "SPARTA", "PUCH", "MATCHLESS", "MACHKLESS",
    "MAKA", "KAWASAKI KAZE", "INDOMOBIL EMOTOR", "HERO PUNCH", "HERO",
    "CF MOTO", "ZUNDAP", "ZHONGYU", "ZETSTAR", "YORIKO", "YMH V75",
    "ROYAL ALLOY", "QJ MOTOR", "PANNONIA", "NORTON", "NIU", "MODENAS",
    "KOKOHFU", "GELIS", "EMOA", "DAVIGO", "CONSUL", "CLEVELAND CYCLEWERKS",
    "BOSSINI", "BLITZER", "BEMBIE", "APRILIA", "ALESSA", "FUKUDA", "HAPPY",
    "TRIUMPH", "SEGWAY",
    # Varian penulisan model Honda/Yamaha/Suzuki lama yang salah masuk field merk
    "HONDA CB 100", "HONDA CB100", "HONDA C86", "HONDA  C86", "HONDA C70",
    "HONDA  C70", "HONDA C100", "HONDA  C100", "HONDA S90", "HONDA LIVE",
    "HONDA GLP II", "HONDA GL100", "HONDA GL 100", "HONDA CB 100 E",
    "HONDA MCB",
    "YAMAHA L 2 S", "YAMAHA L2S", "YAMAHA L2", "YAMAHA L 2", "YAMAHA V 75",
    "YAMAHA V75", "YAMAHA V 80", "YAMAHA V80", "YAMAHA  V80", "YAMAHA LS3",
    "YAMAHA LS 3", "YAMAHA L 2S", "YAMAHA L 2 DX", "YAMAHA RXK",
    "YAMAHA L S 3", "YAMAHA V 50",
    "SUZUKI A100", "SUZUKI A 100", "SUZUKI FR 80", "SUZUKI FR80",
    "SUZUKI RC100", "SUZUKI RC 100", "SUZUKI  RC100", "SUZUKI FR80R",
    "SUZUKI FR 80 N", "SUZUKI A100IX", "SUZUKI A 100 VI", "SUZUKI ST 20",
    "SUZUKI FR70", "SUZUKI FR 70", ",SUZUKI A 100",
}

# Merk mobil/truk/bus yang TIDAK pernah jual sepeda motor di Indonesia.
# (tidak wajib lengkap — default classifier akan anggap merk tak dikenal = mobil)

# Merk yang jual motor SEKALIGUS mobil — perlu cek model.
AMBIGUOUS_BRANDS = {"HONDA", "SUZUKI", "PEUGEOT"}

_HONDA_CAR_KEYWORDS = (
    "BRIO", "JAZZ", "CITY", "CIVIC", "ACCORD", "CR-V", "CRV", "HR-V", "HRV",
    "BR-V", "BRV", "MOBILIO", "FREED", "ODYSSEY", "STREAM", "WRV", "ELYSION",
    "PRELUDE", "INTEGRA", "N-VAN",
    # NB: "LEGEND" sengaja TIDAK dimasukkan — bentrok dengan motor
    # "Honda Legenda/Astrea C100ML LEGENDA" yang jauh lebih umum di data.
)
_SUZUKI_CAR_KEYWORDS = (
    "CARRY", "FUTURA", "APV", "ERTIGA", "BALENO", "IGNIS", "SWIFT", "SX4",
    "XL7", "JIMNY", "KARIMUN", "AERIO", "ESCUDO", "VITARA", "SPLASH", "CIAZ",
    "GC 415", "GC415", "AEV4", "AVI4",
)
_PEUGEOT_MOTOR_KEYWORDS = ("SCOOTER", "SPEEDFIGHT", "KISBEE", "DJANGO")

_BARANG_KEYWORDS = (
    "TRUCK", "TRUK", "PICK UP", "PICK-UP", "PICKUP", "BAK", "TRONTON",
    "TRACTOR", "BOX", "DUMP", "FUSO", "COLT DIESEL", "ENGKEL", "CDD", "CDE",
    "DOUBLE CABIN", "TANGKI",
    # Kode sasis Suzuki Carry/Futura pick-up (bak terbuka) — "AVI4..." dan
    # "GC415T" (varian "T" = truck/pick-up, beda dari "V"/"APV" = minibus).
    "AVI4", "GC415T", "GC 415 T", "GC415 T",
)
_BUS_KEYWORDS = ("MIKROBUS", "MEDIUM BUS", "BIG BUS")
_KHUSUS_KEYWORDS = ("AMBULAN", "PEMADAM", "DEREK", "RESCUE", "JENAZAH", "TANGGA")


def _classify_mobil_subtype(text: str) -> str:
    if "MINIBUS" in text:
        return MOBIL_PENUMPANG
    if any(k in text for k in _KHUSUS_KEYWORDS):
        return KENDARAAN_KHUSUS
    if any(k in text for k in _BARANG_KEYWORDS):
        return MOBIL_BARANG
    if any(k in text for k in _BUS_KEYWORDS) or re.search(r"\bBUS\b", text):
        return MOBIL_BUS
    return MOBIL_PENUMPANG


def classify_by_brand(merk: str | None, model: str | None = None, tipe: str | None = None) -> str | None:
    """
    Fallback classifier untuk region yang API-nya tidak mengembalikan field
    jenis sama sekali (mis. DIY). Berdasarkan riset katalog merk kendaraan
    yang beredar & terdaftar di Indonesia — bukan hasil parsing field resmi,
    jadi dianggap best-effort, bukan ground truth.
    """
    if not merk:
        return None
    m = merk.strip().upper()
    text = f"{model or ''} {tipe or ''}".strip().upper()

    if m in MOTOR_BRANDS:
        return SEPEDA_MOTOR

    if m in AMBIGUOUS_BRANDS:
        if m == "HONDA":
            if any(k in text for k in _HONDA_CAR_KEYWORDS):
                return _classify_mobil_subtype(text)
            return SEPEDA_MOTOR
        if m == "SUZUKI":
            if any(k in text for k in _SUZUKI_CAR_KEYWORDS):
                return _classify_mobil_subtype(text)
            return SEPEDA_MOTOR
        if m == "PEUGEOT":
            if any(k in text for k in _PEUGEOT_MOTOR_KEYWORDS) or "SCOOTERS" in merk.upper():
                return SEPEDA_MOTOR
            return _classify_mobil_subtype(text)

    # Merk tak dikenal (mayoritas brand mobil/truk/bus) → anggap mobil,
    # sub-tipe ditentukan dari kata kunci model/tipe.
    return _classify_mobil_subtype(text)


def infer_jenis(raw_jenis: str | None, merk: str | None = None,
                 model: str | None = None, tipe: str | None = None) -> str | None:
    """Entry point: coba normalisasi raw jenis dulu, fallback ke klasifikasi merk."""
    normalized = normalize_raw_jenis(raw_jenis)
    if normalized:
        return normalized
    return classify_by_brand(merk, model, tipe)
