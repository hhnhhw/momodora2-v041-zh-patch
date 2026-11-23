@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Please install Python 3 first.
  pause
  exit /b 1
)
py -3 apply_patch.py
if errorlevel 1 (
  echo Installation failed. Original files were not overwritten.
) else (
  echo Done. Run momodora2_zh.exe in the game folder.
)
pause
