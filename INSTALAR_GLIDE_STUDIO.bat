@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
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
    if !errorlevel! equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_EXE=py -3"
    )
)

REM -----------------------------------------------------------------------------
REM CENARIO 1: Python está presente -> Usar o instalador gráfico oficial (installer.py)
REM -----------------------------------------------------------------------------
if defined PY_EXE (
    echo [OK] Interpretador Python detectado.
    echo Iniciando o instalador do Glide Studio...
    echo.
    "%PY_EXE%" "%SCRIPT_DIR%installer.py" %*
    if !errorlevel! equ 0 (
        echo.
        echo [SUCESSO] Instalacao concluida com sucesso!
        exit /b 0
    ) else (
        echo.
        echo [AVISO] O processo de instalacao foi encerrado com codigo !errorlevel!.
        pause
        exit /b !errorlevel!
    )
)

REM -----------------------------------------------------------------------------
REM CENARIO 2: Python NÃO está instalado, mas o executável Glide Studio.exe existe
REM -> Instalacao nativa automatica e independente via Windows PowerShell (sem precisar de Python!)
REM -----------------------------------------------------------------------------
set "EXE_SOURCE="
if exist "%SCRIPT_DIR%Glide Studio.exe" (
    set "EXE_SOURCE=%SCRIPT_DIR%Glide Studio.exe"
) else if exist "%SCRIPT_DIR%dist\Glide Studio.exe" (
    set "EXE_SOURCE=%SCRIPT_DIR%dist\Glide Studio.exe"
)

if defined EXE_SOURCE (
    echo [INFO] Python nao detectado, mas o executavel nativo Glide Studio.exe foi localizado!
    echo Instalando o Glide Studio de forma 100%% autonoma no Windows...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$src = '%SCRIPT_DIR%'.TrimEnd('\'); " ^
        "$dst = Join-Path $env:LOCALAPPDATA 'Programs\Glide Studio'; " ^
        "Write-Host '[1/4] Criando diretorio de instalacao em:' $dst -ForegroundColor Cyan; " ^
        "New-Item -ItemType Directory -Path $dst -Force | Out-Null; " ^
        "Write-Host '[2/4] Copiando aplicativo Glide Studio.exe...' -ForegroundColor Cyan; " ^
        "Copy-Item '%EXE_SOURCE%' (Join-Path $dst 'Glide Studio.exe') -Force; " ^
        "Write-Host '[3/4] Instalando ferramentas (FFmpeg, modelos de IA, assets)...' -ForegroundColor Cyan; " ^
        "foreach ($dir in @('tools', 'assets', 'frontend', 'model_packs', 'reference_styles')) { " ^
        "    $sDir = Join-Path $src $dir; " ^
        "    $dDir = Join-Path $dst $dir; " ^
        "    if (Test-Path $sDir) { " ^
        "        if (Test-Path $dDir) { Remove-Item $dDir -Recurse -Force -ErrorAction SilentlyContinue }; " ^
        "        Copy-Item $sDir $dDir -Recurse -Force; " ^
        "    } " ^
        "}; " ^
        "Write-Host '[4/4] Criando atalho na Area de Trabalho e Menu Iniciar...' -ForegroundColor Cyan; " ^
        "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
        "$icoPath = Join-Path $dst 'assets\glide_studio.ico'; " ^
        "$wsh = New-Object -ComObject WScript.Shell; " ^
        "(Join-Path $desktop 'Glide Studio (Modo Navegador).lnk') | Where-Object { Test-Path $_ } | ForEach-Object { Remove-Item $_ -Force }; " ^
        "$sc = $wsh.CreateShortcut((Join-Path $desktop 'Glide Studio.lnk')); " ^
        "$sc.TargetPath = Join-Path $dst 'Glide Studio.exe'; " ^
        "$sc.WorkingDirectory = $dst; " ^
        "if (Test-Path $icoPath) { $sc.IconLocation = $icoPath + ',0' }; " ^
        "$sc.Description = 'Glide Studio - Editor e Renderizador de Video Local'; " ^
        "$sc.Save(); " ^
        "$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Glide Studio'; " ^
        "New-Item -ItemType Directory -Path $startMenu -Force | Out-Null; " ^
        "$scMenu = $wsh.CreateShortcut((Join-Path $startMenu 'Glide Studio.lnk')); " ^
        "$scMenu.TargetPath = Join-Path $dst 'Glide Studio.exe'; " ^
        "$scMenu.WorkingDirectory = $dst; " ^
        "if (Test-Path $icoPath) { $scMenu.IconLocation = $icoPath + ',0' }; " ^
        "$scMenu.Description = 'Glide Studio - Editor e Renderizador de Video Local'; " ^
        "$scMenu.Save(); " ^
        "Write-Host ''; " ^
        "Write-Host '===============================================================================' -ForegroundColor Green; " ^
        "Write-Host '    GLIDE STUDIO INSTALADO COM SUCESSO! ATALHO CRIADO NA AREA DE TRABALHO.     ' -ForegroundColor Green; " ^
        "Write-Host '===============================================================================' -ForegroundColor Green;"

    if !errorlevel! equ 0 (
        echo.
        echo O Glide Studio esta pronto para ser usado.
        echo Pode abrir o aplicativo pelo atalho "Glide Studio" na Area de Trabalho!
        echo.
        pause
        exit /b 0
    ) else (
        echo [ERRO] Ocorreu uma falha durante a instalacao automatica.
        pause
        exit /b !errorlevel!
    )
)

REM -----------------------------------------------------------------------------
REM CENARIO 3: Nem Python nem o executável Glide Studio.exe estão presentes
REM (Exemplo: repositório baixado diretamente do GitHub em máquina totalmente limpa)
REM -----------------------------------------------------------------------------
echo ===============================================================================
echo [AVISO] O interpretador Python nao foi detectado nesta maquina.
echo O repositorio foi baixado do GitHub sem o executavel pre-compilado.
echo.
echo Para colocar o Glide Studio a funcionar neste novo computador:
echo   1. Instale o Python 3.11 no computador (ou via Microsoft Store)
echo   2. Execute novamente este arquivo: INSTALAR_GLIDE_STUDIO.bat
echo.
echo Deseja que o instalador tente instalar o Python 3.11 automaticamente via Windows? (S/N)
set /p INST_PY="> "
if /i "%INST_PY%"=="S" (
    echo Tentando instalar Python 3.11 via winget...
    winget install --id Python.Python.3.11 -e --source winget
    echo.
    echo Se a instalacao do Python terminou, feche esta janela e execute novamente INSTALAR_GLIDE_STUDIO.bat
    pause
    exit /b 0
)

pause
exit /b 1
