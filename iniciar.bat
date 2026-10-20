@echo off
setlocal
title Glide Studio

set "INSTALLED_EXE=%LOCALAPPDATA%\Programs\Glide Studio\Glide Studio.exe"
if exist "%INSTALLED_EXE%" (
    start "" "%INSTALLED_EXE%"
    exit /b 0
)

if exist "%~dp0dist\Glide Studio.exe" (
    start "" "%~dp0dist\Glide Studio.exe"
    exit /b 0
)

echo [AVISO] Glide Studio ainda nao foi instalado localmente.
echo Iniciando o instalador oficial...
call "%~dp0INSTALAR_GLIDE_STUDIO.bat"
exit /b 0
