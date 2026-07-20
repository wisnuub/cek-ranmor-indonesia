@echo off
title Cek Ranmor - Backend API
cd /d "%~dp0backend"
echo Starting FastAPI backend on http://localhost:8000 ...
echo Docs: http://localhost:8000/docs
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
