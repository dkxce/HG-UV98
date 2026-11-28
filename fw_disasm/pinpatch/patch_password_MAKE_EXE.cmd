@echo off
rem Переходим в папку скрипта, чтобы все относительные пути работали откуда угодно.
cd /d "%~dp0"

rem # author  # github.com\dkxce
rem # version # v1.0.0.0

:begin
chcp 65001 >nul
set "PROCESS_NAME=patch_password"

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
.venv\Scripts\create-version-file patch_password.yaml --outfile patch_password.txt
.venv\Scripts\pyinstaller.exe --clean --version-file="patch_password.txt" -i "patch_password.ico" --onefile patch_password.py
@del /Q patch_password.txt
tools\upx.exe -9f dist\patch_password.exe
@echo Сборка завершена
@pause

:end