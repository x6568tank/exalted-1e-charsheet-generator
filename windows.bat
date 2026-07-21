@echo off
setlocal
cd /d "%~dp0"

py -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install -e ".[ui,desktop]" || exit /b 1
.venv\Scripts\python -m PyInstaller pack\exalted-builder.spec || exit /b 1

echo Build complete.
