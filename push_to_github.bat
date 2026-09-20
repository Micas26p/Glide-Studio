@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  GLIDE STUDIO - ENVIANDO COMMITS LOCAIS PARA O GITHUB
echo ============================================================
echo.
git branch -vv
echo.
echo Commits prontos para envio:
git log --oneline origin/main..main
echo.
echo Conectando e enviando para o GitHub (origin main)...
git push origin main
if errorlevel 1 (
    echo.
    echo [ERRO] Falha no push. Se o navegador solicitou login, autorize e tente novamente.
) else (
    echo.
    echo [SUCESSO] Repositorio remoto no GitHub atualizado com sucesso!
)
echo.
pause
