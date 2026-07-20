"""
Known plate suffix patterns per region.
Data ini dikumpulkan dari observasi & komunitas — belum lengkap.
Crawler akan prioritaskan suffix yang ada di sini, lalu brute-force sisanya.

Format suffix: string 1-3 huruf, tanpa I dan O.
Nomor motor vs mobil berdasarkan range (estimasi, bisa dikonfigurasi).
"""

# ---------------------------------------------------------------------------
# Estimasi range nomor per jenis kendaraan
# Beda tiap provinsi tapi ini starting point yang cukup akurat
# ---------------------------------------------------------------------------
NUMBER_RANGES = {
    "mobil":  [(1, 1999), (2000, 3999)],
    "motor":  [(4000, 6999)],
    "khusus": [(7000, 9999)],
    "all":    [(1, 9999)],
}

# ---------------------------------------------------------------------------
# Known suffix patterns per region
# True  = diketahui valid (prioritas pertama)
# False = tidak dipakai / reserved
# None  = unknown (brute force)
# ---------------------------------------------------------------------------

KNOWN_SUFFIXES: dict[str, list[str]] = {

    # ── BALI (DK) ──────────────────────────────────────────────────────────
    # Sumber: observasi komunitas, forum motor Bali
    "bali": [
        # Denpasar Selatan / Utara / Timur / Barat
        "A", "B", "C", "D", "E", "F", "G", "H", "J", "K",
        "L", "M", "N", "P", "Q", "R", "S", "T", "U", "V",
        "W", "X", "Y", "Z",
        # Seri 2 huruf — Denpasar
        "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AJ", "AK",
        "AL", "AM", "AN", "AP", "AQ", "AR", "AS", "AT", "AU", "AV",
        "AW", "AX", "AY", "AZ",
        # Badung (Kuta, Seminyak, Canggu, Nusa Dua)
        "BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BJ", "BK",
        "BL", "BM", "BN", "BP", "BQ", "BR", "BS", "BT", "BU", "BV",
        "BW", "BX", "BY", "BZ",
        # Gianyar (Ubud, Gianyar Kota)
        "CA", "CB", "CC", "CD", "CE", "CF", "CG", "CH", "CJ", "CK",
        # Tabanan
        "DA", "DB", "DC", "DD", "DE", "DF",
        # Buleleng (Singaraja)
        "EA", "EB", "EC", "ED", "EE", "EF", "EG",
        # Klungkung, Bangli, Karangasem
        "FA", "FB", "FC", "FD", "FE", "FF", "FG", "FH",
        "GA", "GB", "GC", "GD",
        "HA", "HB", "HC",
        # Seri 3 huruf (user mention: FCR, ADQ, KK)
        "FCR", "ADQ", "KK",
        # Seri 3 huruf Denpasar lanjutan
        "AAA", "AAB", "AAC", "AAD", "AAE", "AAF", "AAG", "AAH",
        "ABA", "ABB", "ABC", "ABD",
        "ACA", "ACB", "ACC",
        # Badung 3 huruf
        "BAA", "BAB", "BAC", "BAD", "BAE",
        "BBA", "BBB", "BBC",
        "BCA", "BCB",
        # Gianyar 3 huruf
        "CAA", "CAB", "CAC", "CAD",
        # Buleleng 3 huruf
        "EAA", "EAB",
    ],

    # ── JAWA BARAT (D, F, Z, E, T) ─────────────────────────────────────────
    "jabar": [
        # Bandung Kota
        "A", "B", "C", "D", "E", "F", "G", "H", "J", "K",
        "L", "M", "N", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
        # 2 huruf
        "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AJ", "AK",
        "AL", "AM", "AN", "AP", "AQ", "AR", "AS", "AT", "AU", "AV",
        "AW", "AX", "AY", "AZ",
        "BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BJ", "BK",
        "BL", "BM", "BN", "BP", "BQ", "BR", "BS", "BT", "BU", "BV",
        "CA", "CB", "CC", "CD", "CE", "CF",
        "DA", "DB", "DC", "DD",
        "EA", "EB", "EC",
        # 3 huruf populer Jabar
        "AAA", "AAB", "AAC", "AAD", "AAE", "AAF",
        "ABA", "ABB", "ABC",
        "BAA", "BAB", "BAC",
    ],

    # ── JAWA TENGAH (H, G, K, R, AA, AD) ───────────────────────────────────
    "jateng": [
        "A","B","C","D","E","F","G","H","J","K","L","M","N","P","Q","R","S","T","U","V","W","X","Y","Z",
        "AA","AB","AC","AD","AE","AF","AG","AH","AJ","AK",
        "AL","AM","AN","AP","AQ","AR","AS","AT","AU","AV","AW",
        "BA","BB","BC","BD","BE","BF","BG","BH","BJ","BK",
        "CA","CB","CC","CD",
        "DA","DB","DC",
        "EA","EB",
        "AAA","AAB","AAC","AAD",
        "ABA","ABB","ABC",
        "BAA","BAB",
    ],

    # ── DI YOGYAKARTA (AB) ──────────────────────────────────────────────────
    "diy": [
        "A","B","C","D","E","F","G","H","J","K","L","M","N","P","Q","R","S","T","U","V","W","X","Y","Z",
        "AA","AB","AC","AD","AE","AF","AG","AH","AJ","AK",
        "AL","AM","AN","AP","AQ","AR","AS","AT","AU",
        "BA","BB","BC","BD","BE","BF","BG","BH","BJ",
        "CA","CB","CC","CD",
        "DA","DB",
        "AAA","AAB","AAC",
        "ABA","ABB",
    ],
}

# Urutan pencarian: known suffixes dulu, lalu brute force sisa
def get_search_order(region: str) -> tuple[list[str], bool]:
    """
    Returns (known_suffixes, should_bruteforce_remaining).
    """
    known = KNOWN_SUFFIXES.get(region, [])
    return known, True  # selalu brute-force sisanya juga

# Prefix utama per region untuk crawler
REGION_PRIMARY_PREFIX: dict[str, str] = {
    "bali":   "DK",
    "jabar":  "D",
    "jateng": "H",
    "diy":    "AB",
}

# Estimasi jenis kendaraan dari nomor plat
def guess_jenis_from_number(number: int) -> str | None:
    if 1 <= number <= 1999:
        return "Mobil"
    if 2000 <= number <= 3999:
        return "Mobil / Niaga"
    if 4000 <= number <= 6999:
        return "Sepeda Motor"
    if 7000 <= number <= 9999:
        return "Khusus / Dinas"
    return None
