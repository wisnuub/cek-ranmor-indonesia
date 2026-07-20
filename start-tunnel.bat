@echo off
title Cek Ranmor - Cloudflare Tunnel
cd /d "%~dp0"
echo Menghubungkan api-ranmor.fortunamj.com ke localhost:8000 ...
echo.
cloudflared.exe tunnel --config .cloudflared\config.yml run
pause
