@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Please install Python 3 first.
  pause
  exit /b 1
)
py -3 apply_patch.py --remove
if errorlevel 1 (
  echo Uninstall failed. Modified or unrecognized files were preserved.
) else (
  echo Patch files removed. Original game and saves were untouched.
)
pause
