"""
Jakarta soarest3 login helper — pakai Chrome asli via remote debugging.

Cara pakai:
    python jakarta_login.py

Yang terjadi:
  1. Chrome baru terbuka (dengan remote debugging port)
  2. Kamu login Google secara normal (tidak ada automation detection)
  3. Setelah redirect kembali ke soarest3, tekan Enter di sini
  4. Script connect ke Chrome via CDP, extract cookies + localStorage + token
  5. Probe vehicle API, simpan session ke jakarta_session.json

Kenapa CDP, bukan Playwright headless?
  - Google memblokir Playwright/Chromium karena deteksi automation flag
  - Dengan CDP ke Chrome nyata, login dilakukan user sendiri = tidak terdeteksi
"""
import base64
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

SESSION_FILE = Path(__file__).parent / "jakarta_session.json"
SOAREST_BASE = "https://soarest3.jakarta.go.id"
SOAREST_API  = f"{SOAREST_BASE}/api/"

CHROME_EXE       = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DATA = Path.home() / "AppData/Local/Google/Chrome/User Data"
CHROME_STATE     = CHROME_USER_DATA / "Local State"
CDP_PORT         = 9222

# Chrome 96+ moved cookies to Network/Cookies
_COOKIES_CANDIDATES = [
    CHROME_USER_DATA / "Default/Network/Cookies",
    CHROME_USER_DATA / "Default/Cookies",
]
CHROME_COOKIES = next((p for p in _COOKIES_CANDIDATES if p.exists()), _COOKIES_CANDIDATES[0])


# ── Chrome cookie decryption ──────────────────────────────────────────────────

def _get_chrome_key() -> Optional[bytes]:
    if not CHROME_STATE.exists():
        return None
    try:
        state = json.loads(CHROME_STATE.read_text(encoding="utf-8"))
        encrypted_key = base64.b64decode(state["os_crypt"]["encrypted_key"])[5:]
        import win32crypt
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except Exception as e:
        print(f"  [WARN] Gagal ambil Chrome AES key: {e}")
        return None


def _decrypt_value(key: Optional[bytes], enc: bytes) -> str:
    if enc[:3] in (b"v10", b"v11") and key:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM(key).decrypt(enc[3:15], enc[15:], None).decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(enc, None, None, None, 0)[1].decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def get_chrome_cookies_db(domain: str) -> list[dict]:
    if not CHROME_COOKIES.exists():
        print(f"  [WARN] Cookie DB tidak ditemukan: {CHROME_COOKIES}")
        return []
    key = _get_chrome_key()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        shutil.copy2(str(CHROME_COOKIES), tmp_path)
    except PermissionError:
        print("  [WARN] Cookie DB terkunci (Chrome sedang jalan). Gunakan CDP saja.")
        os.unlink(tmp_path)
        return []
    result = []
    try:
        conn = sqlite3.connect(tmp_path)
        rows = conn.execute(
            "SELECT name, encrypted_value, host_key, path, expires_utc, is_secure, is_httponly "
            "FROM cookies WHERE host_key LIKE ?",
            (f"%{domain}%",),
        ).fetchall()
        conn.close()
        for name, enc, host, path, exp, secure, httponly in rows:
            v = _decrypt_value(key, enc)
            if v:
                result.append({"name": name, "value": v, "domain": host,
                                "path": path, "secure": bool(secure), "httpOnly": bool(httponly)})
    except Exception as e:
        print(f"  [WARN] Baca cookie DB gagal: {e}")
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass
    return result


# ── CDP session extraction ────────────────────────────────────────────────────

def extract_via_cdp() -> dict:
    """
    Connect ke Chrome yang sedang jalan via CDP.
    Extract: cookies, localStorage, sessionStorage, Authorization header.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [WARN] playwright tidak terinstall, skip CDP extraction")
        return {}

    print("  Connecting ke Chrome via CDP (localhost:9222)...")
    result = {"cookies": [], "localStorage": {}, "sessionStorage": {}, "authHeader": None}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")

            # Ambil context dan page yang ada di soarest3
            ctx  = browser.contexts[0] if browser.contexts else None
            if not ctx:
                print("  [WARN] Tidak ada browser context ditemukan")
                return result

            # Cookies dari CDP (sudah terdekripsi karena langsung dari browser)
            all_cookies = ctx.cookies()
            soarest_cookies = [c for c in all_cookies if "soarest3" in c.get("domain", "")]
            result["cookies"] = soarest_cookies if soarest_cookies else all_cookies
            print(f"  Cookies via CDP: {len(result['cookies'])} item (soarest3: {len(soarest_cookies)})")

            # Cari page soarest3
            page = None
            for p in ctx.pages:
                if "soarest3" in p.url:
                    page = p
                    break
            if not page and ctx.pages:
                page = ctx.pages[-1]

            if page:
                print(f"  Page aktif: {page.url}")

                # localStorage
                try:
                    ls = page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
                    result["localStorage"] = ls
                    if ls:
                        print(f"  localStorage keys: {list(ls.keys())}")
                except Exception as e:
                    print(f"  [WARN] localStorage: {e}")

                # sessionStorage
                try:
                    ss = page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))")
                    result["sessionStorage"] = ss
                    if ss:
                        print(f"  sessionStorage keys: {list(ss.keys())}")
                except Exception as e:
                    print(f"  [WARN] sessionStorage: {e}")

                # Cari token di storage
                token = None
                for store in (result["localStorage"], result["sessionStorage"]):
                    for k, v in store.items():
                        if any(kw in k.lower() for kw in ("token", "auth", "jwt", "session", "access")):
                            token = v
                            print(f"  Token ditemukan di storage['{k}']: {str(v)[:50]}...")
                            break

                # Coba intercept API call dengan fetch dari page
                print("  Mencoba intercept API call dari page...")
                try:
                    # Test plate: B5651EP → nopa=5651, noph=EP
                    for endpoint in [
                        f"{SOAREST_API}pkb?nopol=B5651EP",
                        f"{SOAREST_API}ranmor?nopol=B5651EP",
                        f"{SOAREST_API}kendaraan?nopol=B5651EP",
                        f"{SOAREST_API}cek?nopol=B5651EP",
                    ]:
                        try:
                            resp = page.evaluate(f"""
                                async () => {{
                                    const r = await fetch('{endpoint}', {{
                                        credentials: 'include',
                                        headers: {{ 'Accept': 'application/json' }}
                                    }});
                                    return {{
                                        status: r.status,
                                        url: r.url,
                                        text: await r.text().catch(() => ''),
                                    }};
                                }}
                            """)
                            status = resp.get("status", 0)
                            text   = resp.get("text", "")[:300]
                            print(f"  [{status}] {endpoint}")
                            if text:
                                print(f"         {text[:150]}")
                            if status == 200 and any(kw in text.lower() for kw in
                                    ("merk", "model", "warna", "pkb", "kendaraan", "motor", "nopol")):
                                result["discovered"] = {
                                    "endpoint": endpoint.split("?")[0],
                                    "method":   "GET",
                                    "params":   {"nopol": "B5651EP"},
                                    "sample":   text,
                                }
                                print(f"  ENDPOINT DITEMUKAN: {endpoint.split('?')[0]}")
                        except Exception as fe:
                            print(f"  [WARN] fetch {endpoint}: {fe}")

                    # Juga coba POST
                    if "discovered" not in result:
                        for endpoint in [f"{SOAREST_API}pkb", f"{SOAREST_API}ranmor"]:
                            try:
                                resp = page.evaluate(f"""
                                    async () => {{
                                        const r = await fetch('{endpoint}', {{
                                            method: 'POST',
                                            credentials: 'include',
                                            headers: {{
                                                'Content-Type': 'application/x-www-form-urlencoded',
                                                'Accept': 'application/json'
                                            }},
                                            body: 'nopol=B5651EP'
                                        }});
                                        return {{ status: r.status, text: await r.text().catch(() => '') }};
                                    }}
                                """)
                                status = resp.get("status", 0)
                                text   = resp.get("text", "")
                                print(f"  [{status}] POST {endpoint}")
                                if text: print(f"         {text[:150]}")
                                if status == 200 and any(kw in text.lower() for kw in
                                        ("merk", "model", "warna", "pkb", "kendaraan")):
                                    result["discovered"] = {
                                        "endpoint": endpoint, "method": "POST",
                                        "params": {"nopol": "B5651EP"}, "sample": text,
                                    }
                            except Exception as pe:
                                print(f"  [WARN] POST {endpoint}: {pe}")

                except Exception as e:
                    print(f"  [WARN] Intercept failed: {e}")

            browser.disconnect()
    except Exception as e:
        print(f"  [ERR] CDP connection gagal: {e}")
        print("        Pastikan Chrome sudah dibuka dengan --remote-debugging-port=9222")

    return result


# ── Chrome launcher ───────────────────────────────────────────────────────────

def launch_chrome_debug():
    """Buka Chrome baru dengan remote debugging, pakai profile yang ada."""
    print("  Membuka Chrome dengan remote debugging port 9222...")
    # Gunakan profile Debug terpisah supaya tidak bentrok dengan Chrome yang mungkin sudah buka
    debug_profile = Path(tempfile.gettempdir()) / "chrome_soarest_debug"
    debug_profile.mkdir(exist_ok=True)

    subprocess.Popen([
        CHROME_EXE,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={debug_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        SOAREST_API,
    ])
    time.sleep(3)  # tunggu Chrome startup


# ── API probe via httpx (fallback jika CDP punya cookies) ────────────────────

def probe_via_httpx(cookies: list[dict]) -> Optional[dict]:
    import httpx
    jar = {c["name"]: c["value"] for c in cookies}
    if not jar:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":     "application/json, */*",
        "Referer":    SOAREST_API,
        "Origin":     SOAREST_BASE,
    }

    candidates = [
        ("GET",  f"{SOAREST_API}pkb",       {"nopol": "B5651EP"}),
        ("GET",  f"{SOAREST_API}ranmor",     {"nopol": "B5651EP"}),
        ("GET",  f"{SOAREST_API}kendaraan",  {"nopol": "B5651EP"}),
        ("GET",  f"{SOAREST_API}cek",        {"nopol": "B5651EP"}),
        ("POST", f"{SOAREST_API}pkb",        {"nopol": "B5651EP"}),
        ("POST", f"{SOAREST_API}ranmor",     {"nopol": "B5651EP"}),
        ("GET",  f"{SOAREST_API}pkb",        {"nopa": "5651", "noph": "EP"}),
    ]

    with httpx.Client(timeout=10, cookies=jar, headers=headers, follow_redirects=False) as client:
        for method, url, params in candidates:
            try:
                r = client.get(url, params=params) if method == "GET" \
                    else client.post(url, data=params)
                print(f"  [{r.status_code}] {method} {url}")
                if r.status_code == 200 and len(r.text) > 20:
                    print(f"         {r.text[:150]}")
                    if any(k in r.text.lower() for k in
                           ("merk", "model", "warna", "pkb", "kendaraan", "motor")):
                        return {"endpoint": url, "method": method,
                                "params": params, "sample": r.text[:500]}
            except Exception as e:
                print(f"  [ERR] {e}")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Jakarta soarest3 — CDP Login Helper")
    print("=" * 60)
    print()
    print("  Script buka Chrome dengan remote debugging supaya")
    print("  kamu bisa login Google tanpa automation detection.")
    print()

    # Cek Chrome ada
    if not Path(CHROME_EXE).exists():
        print(f"  [ERR] Chrome tidak ditemukan di: {CHROME_EXE}")
        print("        Edit CHROME_EXE di script ini sesuai path Chrome kamu.")
        sys.exit(1)

    # Launch Chrome dengan debugging port
    launch_chrome_debug()

    print()
    print("  Chrome terbuka. Langkah:")
    print("  1. Klik 'Sign in with Google'")
    print("  2. Login dengan akun Google seperti biasa")
    print("  3. Setelah redirect balik ke soarest3.jakarta.go.id, ")
    print("     kembali ke sini")
    print()
    input("  Tekan Enter setelah login selesai... ")
    print()

    # Extract via CDP (paling lengkap: cookies + localStorage + fetch intercept)
    print("  Extracting session dari Chrome via CDP...")
    cdp_data = extract_via_cdp()

    cookies = cdp_data.get("cookies", [])
    local_storage  = cdp_data.get("localStorage", {})
    session_storage = cdp_data.get("sessionStorage", {})
    discovered = cdp_data.get("discovered")

    print(f"\n  Cookies: {len(cookies)}")
    for c in cookies[:10]:
        print(f"    {c.get('domain',''):35s} {c.get('name','')}")

    # Kalau CDP punya cookies tapi discovered belum, coba probe via httpx
    if cookies and not discovered:
        print("\n  Probe via httpx dengan cookies CDP...")
        discovered = probe_via_httpx(cookies)

    # Simpan session
    # JWT di localStorage → simpan juga, adapter akan pakai sebagai Bearer token
    token_keys = ["token", "access_token", "accessToken", "jwt", "authToken",
                  "id_token", "idToken", "auth"]
    jwt_token = None
    for store in (local_storage, session_storage):
        for k in token_keys:
            if k in store:
                jwt_token = store[k]
                print(f"\n  JWT token ditemukan di storage['{k}']")
                break
        if jwt_token:
            break

    # Cari di semua localStorage keys jika belum ketemu
    if not jwt_token:
        for store in (local_storage, session_storage):
            for k, v in store.items():
                if isinstance(v, str) and len(v) > 30 and \
                        any(kw in k.lower() for kw in ("token", "auth", "jwt", "key")):
                    jwt_token = v
                    print(f"\n  Possible token di storage['{k}']: {v[:50]}...")
                    break

    session_data = {
        "cookies":        cookies,
        "localStorage":   local_storage,
        "sessionStorage": session_storage,
        "jwt_token":      jwt_token,
        "discovered":     discovered,
        "base_url":       SOAREST_API,
        "saved_at":       time.strftime("%Y-%m-%d %T"),
    }

    SESSION_FILE.write_text(
        json.dumps(session_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  Session disimpan → {SESSION_FILE}")

    if discovered:
        print(f"\n  ENDPOINT DITEMUKAN:")
        print(f"    {discovered['method']} {discovered['endpoint']}")
        print(f"    params: {discovered['params']}")
        print(f"\n  Sample:\n    {discovered['sample'][:300]}")
    elif jwt_token:
        print(f"\n  JWT token tersimpan. Adapter akan pakai sebagai Authorization: Bearer ...")
        print(f"  Perlu update jakarta.py untuk probe endpoint dengan token ini.")
    else:
        print()
        print("  Tidak ada endpoint/token yang terdeteksi otomatis.")
        print("  Buka DevTools di Chrome (F12) → Network tab,")
        print("  cari nomor plat di soarest3, lihat XHR/Fetch request yang muncul.")
        print("  Catat URL endpoint dan method-nya.")

    print()
    print("  Selesai!")


if __name__ == "__main__":
    main()
