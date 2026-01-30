@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   OCR-SoM One-Click Installer (Windows)
echo ============================================================
echo.

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/2] Python not found, installing via winget...
    winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo Failed to install Python automatically.
        echo Please install Python 3.11 manually from:
        echo   https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Python installed! Please restart this script.
    pause
    exit /b 0
)

:: 运行 Python 安装脚本
echo [1/2] Running installer...
python install.py %*

if %errorlevel% neq 0 (
    echo.
    echo Installation failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Quick Start
echo ============================================================
echo.
echo   Start API server:
echo     python server.py
echo.
echo   Then call API:
echo     curl http://localhost:5000/info
echo.
pause
