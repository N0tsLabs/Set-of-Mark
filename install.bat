@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo   PaddleOCR + SoM 一键安装脚本
echo ============================================================
echo.

:: 检查 Python
echo [1/3] 检查 Python 环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   未找到 Python，正在安装...
    winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo   安装 Python 失败，请手动安装 Python 3.11
        pause
        exit /b 1
    )
    echo   Python 安装成功，请重新打开终端后再次运行此脚本
    pause
    exit /b 0
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   %%i
)

:: 安装依赖
echo.
echo [2/3] 安装 PaddleOCR 依赖（首次安装约需 3-5 分钟）...
python -m pip install --upgrade pip -q
python -m pip install paddlepaddle==2.6.2 paddleocr==2.7.3 "numpy<2" opencv-python-headless Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple -q

if %errorlevel% neq 0 (
    echo   依赖安装失败
    pause
    exit /b 1
)
echo   依赖安装成功

:: 测试
echo.
echo [3/3] 测试 PaddleOCR...
python -c "from paddleocr import PaddleOCR; print('  PaddleOCR 导入成功')"

if %errorlevel% neq 0 (
    echo   测试失败
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   安装完成！
echo ============================================================
echo.
echo 使用方法:
echo   python ocr_som.py ^<输入图片^> ^<输出标注图^> ^<输出JSON^>
echo.
echo 示例:
echo   python ocr_som.py screenshot.png marked.png elements.json
echo.
pause
