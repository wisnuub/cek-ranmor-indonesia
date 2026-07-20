"""
Startup script: set env vars then launch uvicorn.
Usage: python run.py
"""
import os
import sys

# ── Crawler config ────────────────────────────────────────────────────────────
os.environ.setdefault("AUTO_CRAWL_REGIONS", "jabar,jateng,diy,bali")
os.environ.setdefault("CRAWL_DELAY",        "1.2")
os.environ.setdefault("CRAWL_MODE",         "all")
os.environ.setdefault("CRAWL_SKIP_AFTER",   "9999")

# ── Start uvicorn ─────────────────────────────────────────────────────────────
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=False)
