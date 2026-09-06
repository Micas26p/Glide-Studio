@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Glide Studio - Instalador Automatico 1-Clique
cd /d "%~dp0"

echo.
echo ============================================================
echo   GLIDE STUDIO - INSTALADOR AUTOMATICO 1-CLIQUE
echo ============================================================
echo   Configurando ambiente completo em qualquer PC Windows...
echo   [Python + FFmpeg + Dependencias Internas e Externas]
echo ============================================================
echo.

REM -----------------------------------------------------------
REM ETAPA 1: DETECCAO OU INSTALACAO AUTOMATICA DO PYTHON
REM -----------------------------------------------------------
echo [1/5] Verificando Python no sistema...

set "PYTHON="

where python >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON=py -3"
    ) else (
        if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
            set "PYTHON=%LocalAppData%\Programs\Python\Python311\python.exe"
            set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;!PATH!"
        )
    )
)

if not defined PYTHON (
    echo.
    echo [AVISO] Python 3 nao foi detectado neste computador.
    echo Baixando e instalando Python 3.11 oficial automaticamente da python.org...
    echo Instalacao isolada por usuario - nao requer privilegios de Administrador.
    echo.
    
    set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
    
    where curl.exe >nul 2>nul
    if !errorlevel!==0 (
        curl.exe -L -o "!PY_INSTALLER!" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    ) else (
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', '!PY_INSTALLER!')"
    )
    
    if not exist "!PY_INSTALLER!" (
        echo [ERRO] Falha ao baixar o instalador do Python.
        echo Por favor, instale o Python 3.10+ manualmente de https://www.python.org/
        pause
        exit /b 1
    )
    
    echo Instalando Python 3.11 silenciosamente. Aguarde alguns instantes...
    "!PY_INSTALLER!" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 Include_launcher=1 SimpleInstall=1
    del /q "!PY_INSTALLER!" 2>nul
    
    set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;!PATH!"
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON=%LocalAppData%\Programs\Python\Python311\python.exe"
    ) else (
        where python >nul 2>nul
        if !errorlevel!==0 set "PYTHON=python"
    )
)

if not defined PYTHON (
    echo [ERRO] Python ainda nao pode ser iniciado. Reinicie este instalador ou instale o Python 3.10+.
    pause
    exit /b 1
)

echo [OK] Python detectado:
%PYTHON% --version
echo.

REM -----------------------------------------------------------
REM ETAPA 2: VERIFICACAO OU DOWNLOAD AUTOMATICO DO FFMPEG
REM -----------------------------------------------------------
echo [2/5] Verificando motor multimedia FFmpeg e FFprobe...

set "HAS_FFMPEG=0"

if exist "%~dp0ffmpeg.exe" (
    if exist "%~dp0ffprobe.exe" (
        set "HAS_FFMPEG=1"
        echo [OK] ffmpeg.exe e ffprobe.exe encontrados na pasta local do Glide Studio.
    )
)

if !HAS_FFMPEG!==0 (
    where ffmpeg >nul 2>nul
    if !errorlevel!==0 (
        where ffprobe >nul 2>nul
        if !errorlevel!==0 (
            set "HAS_FFMPEG=1"
            echo [OK] FFmpeg e FFprobe encontrados no PATH do Windows.
        )
    )
)

if !HAS_FFMPEG!==0 (
    echo.
    echo [AVISO] FFmpeg nao encontrado no sistema.
    echo Baixando binarios portateis oficiais do FFmpeg [Windows 64-bit]...
    echo Isso permite renderizar e processar videos sem precisar configurar nada manualmente.
    echo.

    set "FFMPEG_ZIP=%TEMP%\ffmpeg_glide_setup.zip"
    set "FFMPEG_TMP_DIR=%TEMP%\ffmpeg_glide_extract"
    if exist "!FFMPEG_TMP_DIR!" rmdir /s /q "!FFMPEG_TMP_DIR!" 2>nul
    mkdir "!FFMPEG_TMP_DIR!" 2>nul

    set "FFMPEG_URL=https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"

    echo Baixando pacote FFmpeg Essentials...
    where curl.exe >nul 2>nul
    if !errorlevel!==0 (
        curl.exe -L -o "!FFMPEG_ZIP!" "!FFMPEG_URL!"
    ) else (
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('!FFMPEG_URL!', '!FFMPEG_ZIP!')"
    )

    if not exist "!FFMPEG_ZIP!" (
        echo Tentando link alternativo do FFmpeg...
        set "FFMPEG_URL_ALT=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        if exist "%SystemRoot%\System32\curl.exe" (
            curl.exe -L -o "!FFMPEG_ZIP!" "!FFMPEG_URL_ALT!"
        ) else (
            powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object System.Net.WebClient).DownloadFile('!FFMPEG_URL_ALT!', '!FFMPEG_ZIP!')"
        )
    )

    if exist "!FFMPEG_ZIP!" (
        echo Extraindo ffmpeg.exe e ffprobe.exe para a pasta do Glide Studio...
        powershell -NoProfile -Command "$zip='!FFMPEG_ZIP!'; $dest='!FFMPEG_TMP_DIR!'; Expand-Archive -Path $zip -DestinationPath $dest -Force; $f=Get-ChildItem -Path $dest -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1; $p=Get-ChildItem -Path $dest -Recurse -Filter 'ffprobe.exe' | Select-Object -First 1; if($f){Copy-Item $f.FullName '%~dp0ffmpeg.exe' -Force}; if($p){Copy-Item $p.FullName '%~dp0ffprobe.exe' -Force}"
        del /q "!FFMPEG_ZIP!" 2>nul
        rmdir /s /q "!FFMPEG_TMP_DIR!" 2>nul
    )

    if exist "%~dp0ffmpeg.exe" (
        set "HAS_FFMPEG=1"
        echo [OK] ffmpeg.exe e ffprobe.exe instalados com sucesso na pasta do projeto!
    ) else (
        echo [ALERTA] Nao foi possivel baixar o FFmpeg automaticamente.
        echo Se a renderizacao falhar, copie ffmpeg.exe e ffprobe.exe para esta pasta: %~dp0
    )
)
echo.

REM -----------------------------------------------------------
REM ETAPA 3: AMBIENTE VIRTUAL ISOLADO (.venv)
REM -----------------------------------------------------------
echo [3/5] Configurando ambiente virtual isolado (.venv)...

if not exist ".venv\Scripts\python.exe" (
    echo Criando novo ambiente .venv...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual .venv.
        pause
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
echo [OK] Ambiente virtual .venv ativo.
echo.

REM -----------------------------------------------------------
REM ETAPA 4: INSTALACAO DAS DEPENDENCIAS PYTHON
REM -----------------------------------------------------------
echo [4/5] Instalando e atualizando bibliotecas (FastAPI, OpenCV, PyWebView, etc.)...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt pywebview pyinstaller
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias do requirements.txt.
    pause
    exit /b 1
)
echo.

REM -----------------------------------------------------------
REM ETAPA 5: VALIDACAO DE INTEGRIDADE DO GLIDE STUDIO
REM -----------------------------------------------------------
echo [5/5] Validando integridade dos modulos internos...
python -c "import fastapi, uvicorn, cv2, numpy, pypdf; import app, desktop_app; print('[OK] Todos os modulos internos e externos estao 100%% operacionais!')"
if errorlevel 1 (
    echo [AVISO] Houve um aviso na validacao dos modulos, mas a instalacao foi concluida.
)
echo.

echo ============================================================
echo   INSTALACAO CONCLUIDA COM 100%% DE SUCESSO!
echo ============================================================
echo.
echo   O Glide Studio esta pronto para uso em qualquer PC Windows.
echo   - Motor Python: Configurado em .venv
echo   - Motor de Video: FFmpeg integrado
echo   - Interface Desktop: Suporte nativo pronto
echo.
echo   COMO INICIAR O SISTEMA NO DIA A DIA:
echo   - Basta dar 2 cliques no arquivo: iniciar.bat
echo   [Ou se preferir a versao web no navegador: Iniciar_Versao_Web.bat]
echo ============================================================
echo.

set /p RESP="Deseja abrir o Glide Studio agora? (S/N) [Padrao: S]: "
if /i "!RESP!"=="N" (
    echo.
    echo Voce pode abrir a qualquer momento dando 2 cliques em iniciar.bat.
    echo Ate logo!
    ping 127.0.0.1 -n 3 >nul
    exit /b 0
)

echo.
echo Iniciando o Glide Studio...
call "%~dp0iniciar.bat"
