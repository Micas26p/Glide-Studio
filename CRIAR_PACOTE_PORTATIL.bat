@echo off
chcp 65001 >nul
title Gerar Pacote Instalador Glide Studio (ZIP)
cd /d "%~dp0"

echo ===============================================================================
echo            GERANDO PACOTE OFICIAL COMPLETO GLIDE STUDIO (ZIP)
echo ===============================================================================
echo.

set "PY_EXE="
if exist ".venv-build311\Scripts\python.exe" set "PY_EXE=.venv-build311\Scripts\python.exe"
if "%PY_EXE%"=="" where python >nul 2>&1 && set "PY_EXE=python"
if "%PY_EXE%"=="" where py >nul 2>&1 && set "PY_EXE=py -3"

if "%PY_EXE%"=="" (
    echo [ERRO] Python nao encontrado para gerar o arquivo ZIP.
    pause
    exit /b 1
)

"%PY_EXE%" create_release_zip.py
echo.
pause
