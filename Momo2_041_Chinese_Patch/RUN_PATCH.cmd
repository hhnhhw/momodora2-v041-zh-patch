@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Install Python 3 and run this again.
  pause
  exit /b 1
)
py -3 apply_patch.py --game-dir "%~dp0.."
if errorlevel 1 (
  echo Patch installation failed. No original files were overwritten.
  pause
  exit /b 1
)
start "Momodora II Chinese" "%~dp0..\momodora2_zh.exe"
