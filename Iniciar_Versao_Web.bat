@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Glide Studio Web Local
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Ambiente local ausente. Execute instalar.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, multipart, numpy, cv2" >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Dependencias incompletas. Execute instalar.bat para reparar a instalacao.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" web_app.py
if errorlevel 1 pause
