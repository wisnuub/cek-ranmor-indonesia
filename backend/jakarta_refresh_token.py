"""
Jakarta token refresh - ambil Google ID token dari AccountManager via ADB.

Cara pakai:
    python backend/jakarta_refresh_token.py

Alur:
  Fast path (token masih valid):
    1. Baca accounts_ce.db dari device via ADB
    2. Query ID token untuk client Cek Ranmor DKI
    3. Simpan ke jakarta_session.json (instant, tanpa buka app)

  Slow path (token expired):
    1. Wake + unlock HP dengan PIN (via ADB)
    2. Force-stop + launch app, tunggu silent sign-in refresh token
    3. Baca ulang accounts_ce.db
    4. Sleep layar HP kembali

Syarat:
  - HP tersambung ke PC via ADB wireless (adb connect IP:PORT)
  - App "Cek Ranmor DKI" sudah pernah login dengan Google
  - Root / su tersedia (untuk baca accounts_ce.db milik system)
  - PIN HP disimpan di backend/jakarta_config.json (gitignored)

Token berlaku 1 jam. Jalankan jakarta_token_daemon.py untuk auto-refresh tiap 50 menit.
"""
import base64
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SESSION_FILE = Path(__file__).parent / "jakarta_session.json"
CONFIG_FILE  = Path(__file__).parent / "jakarta_config.json"
APP_PACKAGE  = "com.dki.gov.kominfo.cekranmordki"
PREFS_FILE   = f"/data/data/{APP_PACKAGE}/shared_prefs/{APP_PACKAGE}_preferences.xml"
ACCOUNTS_CE_DB = "/data/system_ce/0/accounts_ce.db"

_SERVER_CLIENT_ID = "869386224620-81v94gi3dhq45h9umr5n8ep6psbqskb5.apps.googleusercontent.com"
_AUTHTOKEN_TYPE   = (
    f"audience:server:client_id:{_SERVER_CLIENT_ID}"
    "?include_email=1&include_profile=1"
)

# Dari jakarta_config.json
_cfg: dict = {}
ADB_DEVICE: str | None = None


# ── Config ─────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    global _cfg
    if CONFIG_FILE.exists():
        try:
            _cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _cfg


# ── Helpers ────────────────────────────────────────────────────────────────────

def adb(*args: str, check=True, capture=True) -> str:
    cmd = ["adb"]
    if ADB_DEVICE:
        cmd += ["-s", ADB_DEVICE]
    cmd += list(args)
    try:
        r = subprocess.run(cmd, capture_output=capture, text=True, timeout=30)
        if check and r.returncode != 0:
            raise RuntimeError(f"adb error: {r.stderr.strip()}")
        return (r.stdout or "").strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("adb timeout")


def _decode_jwt_exp(token: str) -> int:
    try:
        parts = token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(padded))
        return payload.get("exp", 0)
    except Exception:
        return 0


def _token_remaining(token: str) -> int:
    return max(0, _decode_jwt_exp(token) - int(time.time()))


# ── Screen unlock / lock ───────────────────────────────────────────────────────

def _is_screen_on() -> bool:
    out = adb("shell", "dumpsys power", check=False)
    return "mWakefulness=Awake" in out


def _is_locked() -> bool:
    out = adb("shell", "dumpsys window", check=False)
    return "mDreamingLockscreen=true" in out or "isKeyguardShowing=true" in out


def unlock_screen(pin: str) -> bool:
    """
    Wake + unlock HP dengan PIN via ADB.
    Return True jika berhasil (atau sudah unlocked).
    """
    # Wake
    if not _is_screen_on():
        adb("shell", "input keyevent 224")   # KEYEVENT_WAKEUP
        time.sleep(1.2)

    if not _is_locked():
        return True  # sudah unlocked

    # Swipe up untuk reveal PIN entry (Mi 11T Pro: 1080x2400)
    adb("shell", "input swipe 540 1800 540 900")
    time.sleep(0.8)

    # Masukkan PIN
    adb("shell", f"input text {pin}")
    time.sleep(0.4)
    adb("shell", "input keyevent 66")  # Enter
    time.sleep(1.0)

    return not _is_locked()


def sleep_screen():
    """Matikan layar HP kembali."""
    if _is_screen_on():
        adb("shell", "input keyevent 26")   # KEYEVENT_POWER


# ── Token reading ──────────────────────────────────────────────────────────────

def read_token_from_accounts_db() -> str | None:
    """
    Fast path: Baca ID token dari AccountManager (accounts_ce.db) via ADB.
    Tidak perlu launch app. Root diperlukan.
    """
    try:
        b64_out = subprocess.run(
            ["adb"] + (["-s", ADB_DEVICE] if ADB_DEVICE else []) + [
                "exec-out", f"su -c 'base64 {ACCOUNTS_CE_DB}'"
            ],
            capture_output=True, timeout=30,
        )
        if b64_out.returncode != 0 or not b64_out.stdout:
            return None

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        with open(tmp_path, "wb") as f:
            f.write(base64.b64decode(b64_out.stdout))

        conn = sqlite3.connect(tmp_path)
        try:
            account_name = _cfg.get("google_account")
            if account_name:
                row = conn.execute(
                    "SELECT _id FROM accounts WHERE name=? AND type='com.google'",
                    (account_name,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT _id FROM accounts WHERE type='com.google' LIMIT 1"
                ).fetchone()

            if not row:
                return None

            token_row = conn.execute(
                "SELECT authtoken FROM authtokens "
                "WHERE accounts_id=? AND type LIKE ? "
                "ORDER BY rowid DESC LIMIT 1",
                (row[0], f"%{_SERVER_CLIENT_ID}%")
            ).fetchone()

            return token_row[0] if token_row else None
        finally:
            conn.close()
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        print(f"  [WARN] Gagal baca accounts_ce.db: {e}")
    return None


def read_token_from_shared_prefs() -> str | None:
    """Fallback: Baca tokenCredential dari SharedPreferences app."""
    try:
        xml = adb("shell", f"su -c 'cat {PREFS_FILE}'")
        m = re.search(r'name="tokenCredential"[^>]*>([^<]+)', xml)
        if m:
            return m.group(1).strip()
    except Exception as e:
        print(f"  [WARN] Gagal baca SharedPreferences: {e}")
    return None


# ── Token refresh ──────────────────────────────────────────────────────────────

def trigger_token_refresh(pin: str | None) -> bool:
    """
    Slow path: Unlock HP, launch app untuk trigger silent Google Sign-In.
    """
    if pin:
        print("  Unlock layar HP...")
        ok = unlock_screen(pin)
        if ok:
            print("  HP berhasil di-unlock.")
        else:
            print("  [WARN] Unlock mungkin gagal, mencoba launch app tetap...")
    else:
        print("  [WARN] PIN tidak dikonfigurasi - skip unlock.")

    print("  Launch app Cek Ranmor DKI...")
    try:
        adb("shell", f"am force-stop {APP_PACKAGE}")
        time.sleep(0.5)
        adb("shell", f"am start -n {APP_PACKAGE}/.MainActivity")
        print("  Tunggu 8 detik untuk silent sign-in...")
        time.sleep(8)
        return True
    except Exception as e:
        print(f"  [WARN] Gagal launch app: {e}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def check_adb() -> str | None:
    try:
        out = adb("devices", check=False)
        lines = [l for l in out.splitlines() if "\tdevice" in l]
        return lines[0].split("\t")[0] if lines else None
    except Exception:
        return None


def refresh_token() -> bool:
    """Refresh token. Return True jika berhasil."""
    _load_config()
    pin = _cfg.get("device_pin")

    print("=" * 55)
    print("  Jakarta Token Refresh via ADB")
    print("=" * 55)
    print()

    # 1. Cek session saat ini
    current_token = None
    session = {}
    if SESSION_FILE.exists():
        try:
            session = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            current_token = session.get("id_token")
        except Exception:
            pass

    if current_token:
        remaining = _token_remaining(current_token)
        if remaining > 600:
            print(f"  Token masih valid ({remaining // 60} menit sisa). Skip refresh.")
            return True
        elif remaining > 0:
            print(f"  Token sisa {remaining // 60} menit - perlu refresh.")
        else:
            print("  Token expired - refresh diperlukan.")
    else:
        print("  Belum ada token - ambil dari HP.")

    # 2. Cek ADB
    serial = check_adb()
    if not serial:
        print()
        print("  [ERROR] Tidak ada device ADB tersambung.")
        print("  Sambungkan HP via: adb connect IP:PORT")
        return False

    global ADB_DEVICE
    ADB_DEVICE = _cfg.get("adb_device") or serial
    print(f"  Device: {ADB_DEVICE}")
    print()

    # 3. Fast path: baca dari AccountManager DB (tanpa launch app)
    print("  [Fast path] Baca token dari AccountManager...")
    token = read_token_from_accounts_db()

    if token:
        remaining = _token_remaining(token)
        if remaining > 60:
            print(f"  Token valid di AccountManager: {remaining // 60}m {remaining % 60}s sisa")
        else:
            print(f"  Token di AccountManager sudah expired ({remaining}s) - perlu refresh")
            token = None

    # 4. Slow path: unlock + launch app
    if not token:
        print()
        print("  [Slow path] Token expired - refresh via app...")
        trigger_token_refresh(pin)

        print("  Baca token baru dari AccountManager...")
        token = read_token_from_accounts_db()

        if not token:
            print("  Fallback ke SharedPreferences...")
            token = read_token_from_shared_prefs()

        # Tidurkan layar kembali
        print("  Tidurkan layar HP...")
        sleep_screen()

    if not token:
        print()
        print("  [ERROR] Token tidak ditemukan.")
        print("  1. Buka app di HP, login dengan Google")
        print("  2. Pastikan root tersedia")
        return False

    remaining = _token_remaining(token)
    if remaining <= 0:
        print("  [WARN] Token masih expired setelah refresh!")
        print("  Buka app di HP, lakukan pencarian plat, lalu coba lagi.")
        return False
    else:
        print(f"  Token OK: {remaining // 60}m {remaining % 60}s sisa")

    # 5. Simpan session
    exp_ts  = _decode_jwt_exp(token)
    exp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp_ts)) if exp_ts else "unknown"

    session.update({
        "id_token":      token,
        "auth_method":   "bearer_id_token",
        "user_agent":    session.get("user_agent", "myAndroidCk2017"),
        "token_expires": exp_str,
        "refreshed_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "discovered":    session.get("discovered", {
            "token_endpoint":  "https://soarest3.jakarta.go.id/soa/gov.dki.pkb/token",
            "lookup_endpoint": "https://soarest3.jakarta.go.id/soa/gov.dki.pkb/f2501",
            "method":          "GET",
            "url_format":      "{lookup_endpoint}/{PREFIX}/{NOPA}/{NOPH}/NONIK/LIGHT/",
            "auth_header":     "Authorization: Bearer {id_token}",
        }),
        "cookies":  [],
        "base_url": "https://soarest3.jakarta.go.id/soa/gov.dki.pkb/",
    })

    SESSION_FILE.write_text(json.dumps(session, indent=2, ensure_ascii=False), "utf-8")
    print(f"  Disimpan -> {SESSION_FILE.name}")
    print(f"  Expires : {exp_str}")
    print()
    print("  OK.")
    return True


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ADB_DEVICE = sys.argv[1]

    ok = refresh_token()
    sys.exit(0 if ok else 1)
