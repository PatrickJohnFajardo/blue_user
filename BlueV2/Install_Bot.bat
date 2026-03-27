@echo off
setlocal

:: ==========================================
:: BLUE V2 BOT - ONE-CLICK INSTALLER
:: ==========================================

echo.
echo [1/3] Checking Prerequisites...

:: Check 7-Zip
set "SEVENZIP_EXE=C:\Program Files\7-Zip\7z.exe"
if exist "%SEVENZIP_EXE%" (
    echo.    - 7-Zip is already installed.
) else (
    echo.    - 7-Zip NOT FOUND.
    echo.    - Launching 7-Zip Silent Installer...
    start /wait "" "Setup\7z-setup.exe" /S
    echo.    - 7-Zip installed successfully.
)

:: Check Tesseract
set "TESSERACT_EXE=C:\Program Files\Tesseract-OCR\tesseract.exe"
if exist "%TESSERACT_EXE%" (
    echo.    - Tesseract OCR is already installed.
) else (
    echo.    - Tesseract OCR NOT FOUND.
    echo.    - Launching Tesseract Silent Installer...
    :: Note: Tesseract setup supports /S for silent install
    start /wait "" "Setup\tesseract-ocr-w64-setup-5.5.0.20241111.exe" /S
    echo.    - Tesseract OCR installed successfully.
)

echo.
echo [2/3] Preparing Folders...
if not exist "Logs" mkdir "Logs"
if not exist "Data" mkdir "Data"

echo.
echo [3/3] Creating Desktop Shortcut...

set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%Blue.exe"

:: Use PowerShell to find the actual Desktop path (handles OneDrive) and create the shortcut
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut(\"$desktop\Blue.lnk\"); $s.TargetPath = '%EXE_PATH%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

echo.
echo ==========================================
echo INSTALLATION COMPLETE!
echo.
echo You can now find 'Blue' on your Desktop.
echo.
echo IMPORTANT:
echo 1. Keep all files in this folder.
echo 2. Run 'Calibration' inside the bot menu before first use.
echo ==========================================
pause
