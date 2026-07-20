"""
Plate number parser & region router.
Maps Indonesian vehicle plate prefixes to their corresponding region/Samsat.
"""

# Priority: 2-char prefix checked FIRST (e.g. "AB", "AG", "DK")
PLATE_TO_REGION: dict[str, str] = {
    # --- Jawa & Bali ---
    "B": "jakarta",
    "D": "jabar", "F": "jabar", "Z": "jabar", "E": "jabar", "T": "jabar",
    "A": "banten",
    "H": "jateng", "G": "jateng", "K": "jateng", "R": "jateng",
    "AA": "jateng", "AD": "jateng",
    "AB": "diy",
    "L": "jatim", "W": "jatim", "N": "jatim", "P": "jatim",
    "S": "jatim", "M": "jatim",
    "AG": "jatim", "AE": "jatim", "AF": "jatim",
    "DK": "bali",
    # --- Sumatera ---
    "BL": "aceh",
    "BB": "sumut", "BK": "sumut",
    "BA": "sumbar",
    "BM": "riau",
    "BP": "kepri",
    "BH": "jambi",
    "BG": "sumsel",
    "BN": "babel",
    "BE": "lampung",
    # --- Kalimantan ---
    "KB": "kalbar",
    "KH": "kalteng",
    "DA": "kalsel",
    "KT": "kaltim",
    "KU": "kaltara",
    # --- Sulawesi ---
    "DB": "sulut",
    "DM": "gorontalo",
    "DN": "sulteng",
    "DD": "sulsel",
    "DC": "sulbar",
    "DT": "sultra",
    # --- NTB / NTT ---
    "DR": "ntb", "EA": "ntb",
    "DH": "ntt", "EB": "ntt", "ED": "ntt",
    # --- Maluku ---
    "DE": "maluku",
    "DG": "malut",
    # --- Papua ---
    "PA": "papua",
    "PB": "papuabarat",
}

REGION_META: dict[str, dict] = {
    "jakarta":    {"name": "DKI Jakarta",          "needs_nik": False, "supported": True,  "needs_captcha": True},
    "jabar":      {"name": "Jawa Barat",            "needs_nik": False, "supported": True},
    "banten":     {"name": "Banten",                "needs_nik": True,  "supported": True},
    "jateng":     {"name": "Jawa Tengah",           "needs_nik": False, "supported": True},
    "diy":        {"name": "DI Yogyakarta",         "needs_nik": False, "supported": True},
    "jatim":      {"name": "Jawa Timur",            "needs_nik": True,  "supported": True},
    "bali":       {"name": "Bali",                  "needs_nik": False, "supported": True},
    "aceh":       {"name": "Aceh",                  "needs_nik": True,  "supported": False},
    "sumut":      {"name": "Sumatera Utara",        "needs_nik": True,  "supported": False},
    "sumbar":     {"name": "Sumatera Barat",        "needs_nik": True,  "supported": False},
    "riau":       {"name": "Riau",                  "needs_nik": True,  "supported": False},
    "kepri":      {"name": "Kepulauan Riau",        "needs_nik": True,  "supported": False},
    "jambi":      {"name": "Jambi",                 "needs_nik": True,  "supported": False},
    "sumsel":     {"name": "Sumatera Selatan",      "needs_nik": True,  "supported": False},
    "babel":      {"name": "Bangka Belitung",       "needs_nik": True,  "supported": False},
    "lampung":    {"name": "Lampung",               "needs_nik": True,  "supported": False},
    "kalbar":     {"name": "Kalimantan Barat",      "needs_nik": True,  "supported": False},
    "kalteng":    {"name": "Kalimantan Tengah",     "needs_nik": True,  "supported": False},
    "kalsel":     {"name": "Kalimantan Selatan",    "needs_nik": True,  "supported": False},
    "kaltim":     {"name": "Kalimantan Timur",      "needs_nik": True,  "supported": False},
    "kaltara":    {"name": "Kalimantan Utara",      "needs_nik": True,  "supported": False},
    "sulut":      {"name": "Sulawesi Utara",        "needs_nik": True,  "supported": False},
    "gorontalo":  {"name": "Gorontalo",             "needs_nik": True,  "supported": False},
    "sulteng":    {"name": "Sulawesi Tengah",       "needs_nik": True,  "supported": False},
    "sulsel":     {"name": "Sulawesi Selatan",      "needs_nik": True,  "supported": False},
    "sulbar":     {"name": "Sulawesi Barat",        "needs_nik": True,  "supported": False},
    "sultra":     {"name": "Sulawesi Tenggara",     "needs_nik": True,  "supported": False},
    "ntb":        {"name": "Nusa Tenggara Barat",   "needs_nik": True,  "supported": False},
    "ntt":        {"name": "Nusa Tenggara Timur",   "needs_nik": True,  "supported": False},
    "maluku":     {"name": "Maluku",                "needs_nik": True,  "supported": False},
    "malut":      {"name": "Maluku Utara",          "needs_nik": True,  "supported": False},
    "papua":      {"name": "Papua",                 "needs_nik": True,  "supported": False},
    "papuabarat": {"name": "Papua Barat",           "needs_nik": True,  "supported": False},
}


def parse_plate(plate: str) -> tuple[str, str]:
    """Parse plate → (prefix, region_code). Raises ValueError if unknown."""
    clean = "".join(plate.upper().split())
    # 2-char prefix first
    if len(clean) >= 2 and clean[:2] in PLATE_TO_REGION:
        return clean[:2], PLATE_TO_REGION[clean[:2]]
    # 1-char prefix
    if clean and clean[0] in PLATE_TO_REGION:
        return clean[0], PLATE_TO_REGION[clean[0]]
    raise ValueError(f"Prefix plat tidak dikenali untuk: '{plate}'")


def get_region_info(plate: str) -> dict:
    prefix, code = parse_plate(plate)
    meta = REGION_META.get(code, {"name": code.upper(), "needs_nik": True, "supported": False})
    return {"code": code, "prefix": prefix, **meta}
