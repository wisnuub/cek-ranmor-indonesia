@echo off
title Cek Ranmor Indonesia
color 0A
echo.
echo  ================================================
echo   CEK RANMOR INDONESIA - Starting All Services
echo  ================================================
echo.

echo [1/2] Starting FastAPI Backend on port 8000...
start "Ranmor - Backend API" cmd /k "cd /d %~dp0backend && set AUTO_CRAWL_REGIONS=jabar,jateng,diy,bali && set CRAWL_DELAY=1.2 && set CRAWL_MODE=all && set CRAWL_SKIP_AFTER=9999 && python -m uvicorn main:app --host 0.0.0.0 --port 8000 && pause"

timeout /t 5 /nobreak > nul

echo [2/2] Starting Cloudflare Tunnel (api-ranmor.fortunamj.com)...
start "Ranmor - CF Tunnel" cmd /k "cd /d %~dp0 && cloudflared.exe tunnel --config .cloudflared\config.yml run && pause"

echo.
echo  ================================================
echo   Services running:
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo   Public   : https://api-ranmor.fortunamj.com
echo   Frontend : https://ranmor.fortunamj.com
echo.
echo   Auto-crawler aktif: jabar, jateng, diy, bali
echo   Cek progress: GET /admin/crawler/status
echo          Header: x-admin-key: ranmor-admin-2025
echo  ================================================
echo.
echo  Tutup jendela ini untuk stop semua service
echo  (atau tutup masing-masing terminal)
echo.
pause
