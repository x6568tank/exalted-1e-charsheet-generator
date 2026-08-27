@echo off
REM Build a standalone executable. Two products from one tree:
REM   windows.bat          the NiceGUI webapp build  -> dist\ExaltedBuilder.exe
REM   windows.bat qt       the native PySide6 build  -> dist\ExaltedBuilderQt.exe
REM linux.sh is the line-for-line equivalent; keep the two in step.
setlocal
cd /d "%~dp0"

set TARGET=%1
if "%TARGET%"=="" set TARGET=web

py -m venv .venv || exit /b 1

if "%TARGET%"=="qt" (
    .venv\Scripts\python -m pip install -e ".[qt,desktop]" || exit /b 1
    .venv\Scripts\python -m PyInstaller pack\exalted-builder-qt.spec || exit /b 1
    echo Build complete: dist\ExaltedBuilderQt.exe
) else if "%TARGET%"=="web" (
    .venv\Scripts\python -m pip install -e ".[ui,desktop]" || exit /b 1
    .venv\Scripts\python -m PyInstaller pack\exalted-builder.spec || exit /b 1
    echo Build complete: dist\ExaltedBuilder.exe
) else (
    echo usage: windows.bat [web^|qt] 1>&2
    exit /b 2
)
