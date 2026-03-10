@echo off
TITLE Baccarat Bot V2 Launcher
COLOR 0B
CLS

ECHO ======================================================
ECHO      Baccarat Bot V2 - Universal Launcher
ECHO ======================================================
ECHO.

:: 1. Check if Python is installed
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [ERROR] Python is not installed or not in your PATH.
    ECHO.
    ECHO Please install Python 3.10+ from https://www.python.org/
    ECHO.
    ECHO IMPORTANT: When installing, make sure to check the box
    ECHO "Add Python to environment variables" or "Add Python to PATH".
    ECHO.
    PAUSE
    EXIT /B
)

:: 2. Initial Setup if needed
IF NOT EXIST ".venv" (
    ECHO [INFO] First time setup detected. Running setup...
    CALL setup.bat
    IF %ERRORLEVEL% NEQ 0 (
        ECHO [ERROR] Setup failed. Please check the errors above.
        PAUSE
        EXIT /B
    )
    CLS
    ECHO ======================================================
    ECHO      Baccarat Bot V2 - Universal Launcher
    ECHO ======================================================
    ECHO.
)

:: 3. Run Bot
ECHO [INFO] Starting Bot...
.\.venv\Scripts\python.exe main.py launcher
IF %ERRORLEVEL% NEQ 0 (
    ECHO.
    ECHO [ERROR] Bot crashed or closed unexpectedly.
    ECHO If you haven't installed dependencies, run setup.bat manually.
    PAUSE
)
