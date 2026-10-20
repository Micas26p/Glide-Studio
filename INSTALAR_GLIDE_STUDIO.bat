@echo off
setlocal
title Instalador Oficial - Glide Studio

echo ===============================================================================
echo                     INSTALADOR OFICIAL DO GLIDE STUDIO
echo ===============================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PY_EXE="
if exist "%SCRIPT_DIR%.venv-build311\Scripts\python.exe" (
    set "PY_EXE=%SCRIPT_DIR%.venv-build311\Scripts\python.exe"
)

if "%PY_EXE%"=="" (
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    where py >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=py -3"
    )
)

if "%PY_EXE%"=="" (
    echo [ERRO] Interpretador Python nao foi detectado no sistema nem no ambiente virtual.
    echo Por favor, instale o Python 3.10+ ou execute a instalacao via Python.
    pause
    exit /b 1
)

echo Iniciando o instalador do Glide Studio...
"%PY_EXE%" "%SCRIPT_DIR%installer.py" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [AVISO] O processo de instalacao foi cancelado ou encerrou com erro.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Processo concluido!
exit /b 0
