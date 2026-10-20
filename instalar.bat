@echo off
setlocal
cd /d "%~dp0"
call "%~dp0INSTALAR_GLIDE_STUDIO.bat" %*
exit /b %ERRORLEVEL%
