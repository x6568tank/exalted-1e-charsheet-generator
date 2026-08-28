@echo off
REM Build the native PySide6 app as a standalone executable -> dist\ExaltedBuilderQt.exe
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
.venv\Scripts\python -m pip install -e ".[qt,desktop]" || exit /b 1
.venv\Scripts\python -m PyInstaller pack\exalted-builder-qt.spec || exit /b 1
echo Build complete: dist\ExaltedBuilderQt.exe
