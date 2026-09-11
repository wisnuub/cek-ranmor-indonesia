"""
Jakarta soarest3 — ambil Google ID token via Google Identity Services (GSI).

Cara pakai:
    python jakarta_get_token.py

Yang terjadi:
  1. Local web server buka di localhost:9876
  2. Browser terbuka, halaman load Google Sign-In button
  3. Kamu klik "Sign in with Google" (atau One Tap muncul otomatis)
  4. Script dapat id_token dari Google
  5. POST id_token ke soarest3 /token → dapat API token
  6. Test lookup plat B 5651 EP
  7. Simpan ke jakarta_session.json
"""
import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

CLIENT_ID_WEB = "425789725138-o7pgikdb5asq2hooc1rg55kpp5lroa5c.apps.googleusercontent.com"
CLIENT_ID_AND = "869386224620-81v94gi3dhq45h9umr5n8ep6psbqskb5.apps.googleusercontent.com"

PORT          = 9876
SOAREST_BASE  = "https://soarest3.jakarta.go.id"
TOKEN_URL     = f"{SOAREST_BASE}/soa/gov.dki.pkb/token"
LOOKUP_URL    = f"{SOAREST_BASE}/soa/gov.dki.pkb/f2501"
SESSION_FILE  = Path(__file__).parent / "jakarta_session.json"

# ── HTML page ─────────────────────────────────────────────────────────────────

def make_html(client_id: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Jakarta Ranmor — Login</title>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<style>
body {{ font-family: Arial, sans-serif; text-align: center; padding: 60px; background: #f5f5f5; }}
h2 {{ color: #333; }}
#status {{ margin-top: 20px; color: #666; font-size: 14px; }}
#result {{ margin-top: 20px; font-size: 12px; color: green; word-break: break-all; }}
</style>
</head>
<body>
<h2>Jakarta Cek Ranmor — Google Login</h2>
<p>Klik tombol di bawah untuk login, atau tunggu One Tap muncul otomatis.</p>

<div id="g_id_onload"
     data-client_id="{client_id}"
     data-callback="handleCredential"
     data-auto_prompt="true"
     data-auto_select="true">
</div>
<div class="g_id_signin"
     data-type="standard"
     data-size="large"
     data-theme="outline"
     data-text="sign_in_with"
     data-shape="rectangular">
</div>

<div id="status">Menunggu login...</div>
<div id="result"></div>

<script>
function handleCredential(response) {{
    const token = response.credential;
    document.getElementById('status').textContent = 'Token diterima! Mengirim ke server...';
    document.getElementById('result').textContent = 'id_token: ' + token.substring(0, 60) + '...';

    fetch('/token', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{id_token: token}})
    }})
    .then(r => r.json())
    .then(data => {{
        if (data.ok) {{
            document.getElementById('status').textContent = 'Berhasil! Tutup tab ini.';
            document.getElementById('result').style.color = 'green';
        }} else {{
            document.getElementById('status').textContent = 'Token dikirim: ' + JSON.stringify(data);
        }}
    }})
    .catch(e => {{
        document.getElementById('status').textContent = 'Error: ' + e;
    }});
}}
</script>
</body>
</html>"""

# ── Local server ──────────────────────────────────────────────────────────────

_received_token = None
_server         = None


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            # Serve the Google Sign-In page
            for cid in [CLIENT_ID_WEB, CLIENT_ID_AND]:
                body = make_html(cid).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        global _received_token
        if self.path == "/token":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body)
                _received_token = data.get("id_token")
                response = json.dumps({"ok": True}).encode()
            except Exception as e:
                response = json.dumps({"error": str(e)}).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(response))
            self.end_headers()
            self.wfile.write(response)

            # Signal server to stop
            threading.Thread(target=_server.shutdown, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


# ── soarest3 token exchange ───────────────────────────────────────────────────

def post_to_soarest(id_token: str) -> tuple[str | None, dict]:
    """POST id_token ke soarest3 /token. Return (api_token, raw_response)."""
    headers = {
        "User-Agent":   "okhttp/4.12.0",
        "Accept":       "application/json",
        "Content-Type": "application/json",
    }
    formats = [
        {"id_token":     id_token},
        {"credential":   id_token},
        {"token":        id_token},
        {"google_token": id_token},
    ]
    with httpx.Client(timeout=15) as c:
        for payload in formats:
            key = list(payload.keys())[0]
            try:
                r = c.post(TOKEN_URL, json=payload, headers=headers)
                print(f"  POST /token ({key}): [{r.status_code}] {r.text[:200]}")
                data = r.json()
                if isinstance(data, dict) and str(data.get("status")) == "1":
                    # Success! Extract API token
                    for k in ("token", "access_token", "api_token", "data"):
                        if k in data and data[k]:
                            return data[k], data
                    return id_token, data  # fallback: use id_token directly
            except Exception as e:
                print(f"  [ERR] POST /token ({key}): {e}")
    return None, {}


def test_vehicle_lookup(bearer_token: str) -> dict | None:
    """Test lookup B 5651 EP."""
    url = f"{LOOKUP_URL}/B/5651/EP/NONIK/LIGHT/"
    headers = {
        "User-Agent":    "okhttp/4.12.0",
        "Accept":        "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }
    with httpx.Client(timeout=15) as c:
        r = c.get(url, headers=headers)
        print(f"  GET {url}")
        print(f"  [{r.status_code}] {r.text[:300]}")
        try:
            d = r.json()
            if str(d.get("status")) == "1":
                return d
        except Exception:
            pass
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _server, _received_token

    print("=" * 60)
    print("  Jakarta — Google ID Token via GSI")
    print("=" * 60)
    print()
    print("  Script ini pakai Google Identity Services (GSI)")
    print("  — sign-in via halaman web lokal, tidak ada automation detection.")
    print()

    _received_token = None
    _server = http.server.HTTPServer(("localhost", PORT), _Handler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()

    url = f"http://localhost:{PORT}/"
    print(f"  Membuka browser: {url}")
    webbrowser.open(url)

    print(f"  Menunggu kamu login Google di browser (maks 5 menit)...")
    deadline = time.time() + 300
    while _received_token is None and time.time() < deadline:
        time.sleep(0.5)

    if not _received_token:
        print("  [TIMEOUT] Tidak ada token diterima.")
        print("  Kemungkinan: client_id tidak mengijinkan localhost origin.")
        print()
        print("  Alternatif: jalankan menggunakan --android-client")
        return

    print(f"\n  id_token diterima: {_received_token[:50]}...")
    print()

    # POST ke soarest3
    print("  Mengirim ke soarest3 /token...")
    api_token, soarest_resp = post_to_soarest(_received_token)

    # Coba lookup
    print()
    print("  Test lookup B 5651 EP...")
    vehicle = None

    for tok in filter(None, [api_token, _received_token]):
        vehicle = test_vehicle_lookup(tok)
        if vehicle:
            break

    # Simpan session
    session = {
        "id_token":       _received_token,
        "api_token":      api_token,
        "soarest_token":  soarest_resp,
        "vehicle_sample": vehicle,
        "discovered": {
            "endpoint":    LOOKUP_URL,
            "method":      "GET",
            "url_format":  "{endpoint}/{prefix}/{nopa}/{noph}/NONIK/LIGHT/",
            "auth_header": "Authorization: Bearer {token}",
            "which_token": "api_token or id_token",
        },
        "cookies":  [],
        "base_url": f"{SOAREST_BASE}/soa/gov.dki.pkb/",
        "saved_at": time.strftime("%Y-%m-%d %T"),
    }
    SESSION_FILE.write_text(json.dumps(session, indent=2, ensure_ascii=False), "utf-8")
    print(f"\n  Session disimpan → {SESSION_FILE}")

    if vehicle:
        print(f"\n  VEHICLE DATA:")
        for k, v in vehicle.items():
            if v:
                print(f"    {k}: {v}")
    elif api_token:
        print(f"\n  API token tersimpan. Adapter perlu di-update untuk pakai /f2501/ endpoint.")
    else:
        print(f"\n  id_token tersimpan tapi belum bisa akses vehicle API.")
        print(f"  Soarest3 mungkin pakai Google ID token dari Android Sign-In (bukan web).")


if __name__ == "__main__":
    main()
