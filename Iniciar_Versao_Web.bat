@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Glide Studio Web Local v1.28.2
cd /d "%~dp0"

set PORT=8787

echo.
echo ============================================================
echo  GLIDE STUDIO - VERSAO WEB LOCAL v1.28.2
echo ============================================================
echo  Use este BAT somente para abrir a versao web/fallback.
echo  Para a versao desktop, abra Glide Studio.exe nesta pasta inicial.
echo.

echo [0/6] Limpando servidor antigo na porta %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
  echo Encerrando processo antigo PID %%a na porta %PORT%...
  taskkill /PID %%a /F >nul 2>nul
)
timeout /t 1 /nobreak >nul

where python >nul 2>nul
if %errorlevel%==0 (
  set PYTHON=python
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set PYTHON=py -3
  ) else (
    echo [ERRO] Python nao encontrado.
    echo Instale Python 3.10+ e marque a opcao Add Python to PATH.
    pause
    exit /b 1
  )
)

echo [1/6] Python detectado:
%PYTHON% --version

echo.
echo [2/6] Verificando FFmpeg...
where ffmpeg >nul 2>nul
if %errorlevel%==0 (
  ffmpeg -version | findstr /i "ffmpeg version"
  echo [OK] FFmpeg encontrado no PATH.
) else (
  if exist "%~dp0ffmpeg.exe" (
    echo [OK] ffmpeg.exe encontrado na pasta do Glide Ultra.
  ) else (
    echo [AVISO] FFmpeg nao foi encontrado.
    echo Para renderizar, instale FFmpeg e adicione ao PATH, ou coloque ffmpeg.exe e ffprobe.exe nesta pasta.
    echo Link recomendado: https://www.gyan.dev/ffmpeg/builds/
  )
)

echo.
echo [3/6] Preparando ambiente virtual...
if not exist ".venv\Scripts\python.exe" (
  %PYTHON% -m venv .venv
  if errorlevel 1 (
    echo [ERRO] Falha ao criar .venv
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"

echo.
echo [4/6] Instalando/validando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo.
echo [5/6] Abrindo o Glide Ultra Web no navegador...
start "" "http://127.0.0.1:%PORT%/?v=1.28.2"
echo.
echo Servidor local: http://127.0.0.1:%PORT%
echo Pasta de exports: %~dp0exports
echo Pasta legacy renders: %~dp0renders
echo.
echo Para encerrar a versao web, feche esta janela ou pressione CTRL+C.
echo ============================================================
echo.

echo [6/6] Iniciando servidor...
uvicorn app:app --host 127.0.0.1 --port %PORT%

echo.
echo [FIM] O servidor foi encerrado.
pause




