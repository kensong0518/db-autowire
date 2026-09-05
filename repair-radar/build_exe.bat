@echo off
chcp 65001 >nul
title 打包成單一 exe
cd /d "%~dp0"

echo.
echo   把維修接單台打包成單一 exe，不需要對方電腦有 Python。
echo   需要網路連線下載 PyInstaller，第一次約 2-3 分鐘。
echo.
pause

where py >nul 2>&1 && (set PY=py) || (set PY=python)

echo.
echo   [1/2] 安裝 PyInstaller...
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 goto fail

echo.
echo   [2/2] 打包中...
%PY% -m PyInstaller --onefile --name RepairRadar ^
  --add-data "web;web" ^
  --add-data "keywords.json;." ^
  --add-data "config.example.json;." ^
  --collect-submodules sqlite3 ^
  repair_radar.py
if errorlevel 1 goto fail

echo.
echo   完成。dist\RepairRadar.exe 就是成品，可以改名成中文。
echo   注意：exe 是未簽章的，Windows SmartScreen 會跳警告，
echo   按「其他資訊」再按「仍要執行」即可。
echo.
pause
exit /b

:fail
echo.
echo   打包失敗。確認電腦有 Python 且能連上網路。
echo.
pause
