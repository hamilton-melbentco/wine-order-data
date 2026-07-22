@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo           Wine Order Extractor Launcher
echo ===================================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python before running this application.
    pause
    exit /b
)

:: Define virtual environment folder
set "VENV_DIR=.venv"

:: Create the virtual environment if it doesn't exist yet
if exist "%VENV_DIR%" (
    echo [INFO] Virtual environment found.
    echo [INFO] Activating environment...
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [INFO] No virtual environment found. Setting one up...
    python -m venv %VENV_DIR%
    echo [INFO] Activating environment...
    call "%VENV_DIR%\Scripts\activate.bat"
    echo [INFO] Upgrading pip...
    python -m pip install --upgrade pip
)

:: Always make sure dependencies are present (instant if already installed).
:: This is what lets the clipboard-paste feature install on existing setups.
echo [INFO] Checking dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    pip install streamlit google-genai pillow streamlit-paste-button
)

echo [INFO] Launching your Streamlit App...
echo ===================================================
streamlit run app.py

pause
