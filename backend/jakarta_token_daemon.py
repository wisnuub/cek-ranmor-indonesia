"""
Jakarta Token Daemon - auto-refresh Google ID token tiap 50 menit.

Cara pakai:
    python backend/jakarta_token_daemon.py

Daemon ini:
  - Refresh token segera saat start
  - Loop tiap 50 menit (sebelum token 1 jam expire)
  - Kalau refresh gagal: retry tiap 5 menit
  - Kalau ADB putus: retry terus sampai nyambung lagi
  - Windows toast notification saat refresh berhasil/gagal

Stop: Ctrl+C
"""
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REFRESH_SCRIPT   = Path(__file__).parent / "jakarta_refresh_token.py"
REFRESH_INTERVAL = 50 * 60   # 50 menit (normal)
RETRY_INTERVAL   = 5  * 60   # 5 menit (kalau gagal)

WIB = timezone(timedelta(hours=7))


# ── Windows notification ────────────────────────────────────────────────────────

def notify(title: str, msg: str, icon: str = "Info"):
    """
    Windows balloon/toast notification via PowerShell.
    Tidak butuh package tambahan. Jalan di background (non-blocking).
    icon: Info | Warning | Error | None
    """
    # Escape single quotes untuk PowerShell
    title = title.replace("'", "`'")
    msg   = msg.replace("'", "`'")
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$n = [System.Windows.Forms.NotifyIcon]::new();"
        "$n.Icon = [System.Drawing.SystemIcons]::Information;"
        "$n.Visible = $true;"
        f"$n.ShowBalloonTip(7000, '{title}', '{msg}', "
        f"[System.Windows.Forms.ToolTipIcon]::{icon});"
        "Start-Sleep -Seconds 8;"
        "$n.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Notification gagal tidak boleh crash daemon


def ts() -> str:
    return datetime.now(WIB).strftime("%H:%M:%S")


def is_maintenance() -> bool:
    """Cek apakah soarest3 sedang maintenance."""
    now = datetime.now(WIB)
    day, h = now.weekday(), now.hour  # 0=Mon ... 6=Sun
    return (
        (day in [0, 1, 2, 3] and h >= 22) or   # Senin-Kamis 22:00-00:00
        (day == 4 and h >= 19) or               # Jumat 19:00-00:00
        (day == 5 and 13 <= h < 16)             # Sabtu 13:00-16:00
    )


def run_refresh() -> bool:
    """Jalankan refresh script. Return True jika sukses."""
    result = subprocess.run(
        [sys.executable, str(REFRESH_SCRIPT)],
        capture_output=False,
    )
    return result.returncode == 0


def main():
    print("=" * 55)
    print("  Jakarta Token Daemon")
    print(f"  Refresh setiap {REFRESH_INTERVAL // 60} menit")
    print("  Stop: Ctrl+C")
    print("=" * 55)
    print()

    notify(
        "Jakarta Token Daemon",
        f"Daemon aktif. Auto-refresh tiap {REFRESH_INTERVAL // 60} menit.",
        "Info",
    )

    consecutive_fails = 0

    while True:
        print(f"\n[{ts()}] -- Token refresh --")

        if is_maintenance():
            now = datetime.now(WIB)
            print(f"  Server maintenance ({now.strftime('%A %H:%M')} WIB) - skip, tunggu 10 menit...")
            time.sleep(10 * 60)
            continue

        ok = run_refresh()

        if ok:
            consecutive_fails = 0
            next_time = datetime.now(WIB) + timedelta(seconds=REFRESH_INTERVAL)
            print(f"\n  Next refresh: {next_time.strftime('%H:%M')} WIB")
            notify(
                "Jakarta Token OK",
                f"Token refreshed. Next: {next_time.strftime('%H:%M')} WIB.",
                "Info",
            )
            time.sleep(REFRESH_INTERVAL)
        else:
            consecutive_fails += 1
            print(f"\n  [GAGAL #{consecutive_fails}] Retry dalam {RETRY_INTERVAL // 60} menit...")

            warn_msg = f"Refresh gagal #{consecutive_fails}! Cek koneksi HP / ADB."
            if consecutive_fails >= 3:
                warn_msg = (
                    f"Refresh gagal {consecutive_fails}x berturut! "
                    "Sambungkan HP via ADB dan pastikan app sudah login."
                )
            notify("Jakarta Token GAGAL", warn_msg, "Warning")

            if consecutive_fails >= 5:
                print("  [WARN] Sudah gagal 5x berturut-turut!")
                print("  Pastikan HP tersambung ADB dan app sudah login.")
            time.sleep(RETRY_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n[{ts()}] Daemon dihentikan.")
        sys.exit(0)
