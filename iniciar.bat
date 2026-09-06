@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Glide Studio Local
cd /d "%~dp0"

echo.
echo ============================================================
echo   GLIDE STUDIO - INICIAR
echo ============================================================
echo.

set PORT=8787

REM Limpar eventual processo antigo na porta 8787
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>nul
)

REM 1. Se existir o binario compilado Glide Studio.exe, prioriza-lo
if exist "%~dp0Glide Studio.exe" (
    echo Iniciando Glide Studio [Desktop Executavel]...
    start "" "%~dp0Glide Studio.exe"
    exit /b 0
)

REM 2. Se nao existir o EXE compilado, verificar o ambiente virtual .venv
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [AVISO] O ambiente do Glide Studio ainda nao foi instalado neste computador.
    echo.
    set /p INST="Deseja executar a instalacao automatica 1-clique agora? (S/N) [Padrao: S]: "
    if /i "!INST!"=="N" (
        echo Para instalar mais tarde, execute o arquivo instalar.bat.
        pause
        exit /b 1
    )
    call "%~dp0instalar.bat"
    exit /b 0
)

REM 3. Executar via desktop_app.py no ambiente .venv
call "%~dp0.venv\Scripts\activate.bat"

echo Iniciando Glide Studio [Desktop Nativo]...
python "%~dp0desktop_app.py"

if errorlevel 1 (
    echo.
    echo [AVISO] Ocorreu uma interrupcao. Se preferir a versao web, use Iniciar_Versao_Web.bat.
    pause
)
