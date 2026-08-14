@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Generating application icon...
python build_icon.py
if errorlevel 1 goto :error

echo [2/4] Installing runtime dependencies...
python -m pip install PyQt6 PyAudioWPatch keyboard pyperclip pydantic numpy cffi
if errorlevel 1 goto :error

echo [3/4] Installing packaging tools...
python -m pip install pyinstaller
if errorlevel 1 goto :error

echo [4/4] Building single-file executable with PyInstaller...
python -m PyInstaller --noconfirm --clean FlowAI.spec
if errorlevel 1 goto :error

echo [5/5] Installing to %APPDATA%\FlowAI and creating desktop shortcut...
python create_shortcut.py
if errorlevel 1 goto :error

echo.
echo Build complete: %~dp0dist\FlowAI.exe
echo Installed to: %APPDATA%\FlowAI\FlowAI.exe (stable, unblocked)
echo A desktop shortcut "FlowAI" has been created.
echo.
echo Equivalent direct command:
echo   pyinstaller --noconsole --onefile --icon assets\app.ico --name FlowAI main.py
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
