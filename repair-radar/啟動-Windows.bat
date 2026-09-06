@echo off
chcp 65001 >nul
title 維修接單台
cd /d "%~dp0"

where py >nul 2>&1 && (py repair_radar.py & goto :eof)
where python >nul 2>&1 && (python repair_radar.py & goto :eof)

echo.
echo   找不到 Python，請先安裝再執行這個檔案。
echo.
echo   1. 到 https://www.python.org/downloads/ 下載
echo   2. 安裝時務必勾選 "Add Python to PATH"
echo   3. 裝完重新雙擊這個檔案
echo.
pause
