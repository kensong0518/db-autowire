@echo off
title Repair Radar Installer
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1"
if errorlevel 1 (
  echo.
  echo Installer failed to launch. Right-click this file and choose "Run as administrator".
  pause
)
