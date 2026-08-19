@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Build Glide Studio Desktop
cd /d "%~dp0"

echo.
echo ============================================================
echo  GLIDE STUDIO - BUILD DESKTOP WINDOWS
echo ============================================================
echo.

set "LOCAL_PY=%CD%\.uv-python\cpython-3.11.15-windows-x86_64-none\python.exe"
if exist "%LOCAL_PY%" (
  set "PYTHON=%LOCAL_PY%"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3.11 --version >nul 2>nul
    if !errorlevel! == 0 (
      set "PYTHON=py -3.11"
    )
  )
  if not defined PYTHON (
    where python >nul 2>nul
    if !errorlevel! == 0 (
      set "PYTHON=python"
    )
  )
  if not defined PYTHON (
    echo [ERRO] Python nao encontrado.
    echo Instale Python 3.11+ ou mantenha a pasta .uv-python gerada pelo projeto.
    pause
    exit /b 1
  )
)

echo [1/5] Python:
%PYTHON% --version

echo.
echo [2/5] Criando ambiente de build...
set "VENV_DIR=.venv-build311"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  %PYTHON% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ERRO] Falha ao criar %VENV_DIR%
    pause
    exit /b 1
  )
)
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo [3/5] Instalando dependencias...
python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt pyinstaller pywebview
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo.
echo [4/5] Validando codigo...
python -m py_compile app.py desktop_app.py
if errorlevel 1 (
  echo [ERRO] Validacao falhou.
  pause
  exit /b 1
)

echo.
echo [5/5] Gerando app principal Glide Studio.exe...
pyinstaller --clean --noconfirm --distpath "%CD%" GlideUltra.spec
if errorlevel 1 (
  echo [ERRO] PyInstaller falhou.
  pause
  exit /b 1
)

echo.
echo Limpando artefatos temporarios do build...
if exist "%CD%\build" rmdir /s /q "%CD%\build"
if exist "%CD%\__pycache__" rmdir /s /q "%CD%\__pycache__"
del /q "%CD%\build_*.log" 2>nul

echo.
echo ============================================================
echo  Build concluido.
echo  App principal: %~dp0Glide Studio.exe
echo  Ao abrir o EXE, ele inicia o motor local em uma janela nativa.
echo.
echo  FFmpeg:
echo  - Se ja estiver no PATH, o app vai encontrar automaticamente.
echo  - Ou copie ffmpeg.exe e ffprobe.exe para esta pasta inicial.
echo ============================================================
pause
