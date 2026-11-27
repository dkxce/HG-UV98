@echo off
rem Переходим в папку скрипта, чтобы все относительные пути работали откуда угодно.
cd /d "%~dp0"

rem # author  # github.com\dkxce
rem # version # v1.0.0.0

:begin
chcp 65001 >nul
set "PROCESS_NAME=replace_splash"

:iflaunched
tasklist /nh /fi "imagename eq %PROCESS_NAME%.exe" 2>nul | findstr /i "%PROCESS_NAME%" >nul
if %errorlevel% neq 0 goto build
echo Процесс %PROCESS_NAME% сейчас запущен.
set /p "choice=Остановить его и запустить сборку exe? [Y/N]: "
if /i "%choice%"=="Y" (
    powershell -Command "Stop-Process -Name %PROCESS_NAME% -Force"
	goto build
) else exit /b	

:build
@echo on
.venv\Scripts\create-version-file replace_splash.yaml --outfile replace_splash.txt
.venv\Scripts\pyinstaller.exe --clean --version-file="replace_splash.txt" -i "replace_splash.ico" --onefile replace_splash.py
@del /Q replace_splash.txt
tools\upx.exe -9f dist\replace_splash.exe
@echo Сборка завершена
@pause

:end