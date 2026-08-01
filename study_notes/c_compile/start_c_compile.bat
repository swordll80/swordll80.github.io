@echo off
setlocal
cd /d "%~dp0\..\.."
where python >nul 2>&1
if errorlevel 1 (
  echo Python 3 was not found. Please install Python 3 and try again.
  pause
  exit /b 1
)
echo Starting the local C compiler bridge...
python study_notes\compile_server.py --page study_notes/c_compile/index.html --open
pause
