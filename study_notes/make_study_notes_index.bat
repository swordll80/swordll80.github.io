@echo off
setlocal

rem Run the generator from the directory where this BAT file is located.
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_study_notes_index.ps1"
if errorlevel 1 (
    echo.
    echo Index generation failed. See the error above.
) else (
    echo.
    echo Index generated: study_notes_index.html
)

pause
