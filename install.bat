@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   OCR-SoM 一键安装程序 (Windows)
echo ============================================================
echo.
echo   此脚本将自动：
echo   - 检测 Python 环境
echo   - 检测 NVIDIA GPU
echo   - 安装 PaddlePaddle (GPU/CPU 版本)
echo   - 安装 cuDNN 库 (如果使用 GPU)
echo   - 安装 PaddleOCR 及其他依赖
echo.

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，正在通过 winget 安装...
    winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo 自动安装 Python 失败！
        echo 请手动从以下地址下载安装 Python 3.11：
        echo   https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    echo.
    echo Python 安装完成！请重新运行此脚本。
    pause
    exit /b 0
)

:: 显示 Python 版本
python --version

:: 运行 Python 安装脚本
echo.
echo 正在运行安装程序...
echo.
python install.py %*

if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo   安装失败！
    echo ============================================================
    echo.
    echo   可能的解决方法：
    echo   1. 确保 Python 版本为 3.9-3.12
    echo   2. 尝试使用 CPU 版本: install.bat --cpu
    echo   3. 检查网络连接
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   快速开始
echo ============================================================
echo.
echo   启动服务器：
echo     python server.py
echo.
echo   然后打开浏览器访问：
echo     http://127.0.0.1:5000
echo.
echo   命令行参数：
echo     --cpu    强制使用 CPU 版本
echo     --gpu    强制使用 GPU 版本
echo.
pause
