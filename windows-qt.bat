@echo off
REM Build the native PySide6 app as a standalone executable -> dist\ExaltedBuilderQt.exe
setlocal
cd /d "%~dp0"

py -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install -e ".[qt,desktop]" || exit /b 1
.venv\Scripts\python -m PyInstaller pack\exalted-builder-qt.spec || exit /b 1
echo Build complete: dist\ExaltedBuilderQt.exe
