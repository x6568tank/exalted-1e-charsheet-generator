@echo off
REM Build the NiceGUI webapp as a standalone executable -> dist\ExaltedBuilder.exe
REM
REM TWO PRODUCTS build from this tree, one script each:
REM   linux.sh        linux-qt.sh         (Linux/macOS)
REM   windows.bat     windows-qt.bat      (Windows)
REM Keep all FOUR in step - they differ only in the extras and the spec.
REM
REM One script per product rather than an argument, because a .bat that needs one
REM cannot be DOUBLE-CLICKED: `windows.bat qt` meant opening a terminal, which is
REM the thing a .bat exists to avoid.
setlocal
cd /d "%~dp0"

py -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install -e ".[ui,desktop]" || exit /b 1
.venv\Scripts\python -m PyInstaller pack\exalted-builder.spec || exit /b 1
echo Build complete: dist\ExaltedBuilder.exe
