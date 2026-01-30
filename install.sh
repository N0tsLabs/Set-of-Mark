#!/bin/bash
#
# OCR-SoM 跨平台一键安装脚本 (Linux/macOS)
#
# 此脚本将自动：
# - 检测 Python 环境
# - 检测 NVIDIA GPU
# - 安装 PaddlePaddle (GPU/CPU 版本)
# - 安装 cuDNN 库 (如果使用 GPU)
# - 安装 PaddleOCR 及其他依赖
#
# 使用方法:
#   chmod +x install.sh
#   ./install.sh          # 自动检测并安装
#   ./install.sh --cpu    # 强制使用 CPU 版本
#   ./install.sh --gpu    # 强制使用 GPU 版本
#

set -e

echo "============================================================"
echo "  OCR-SoM 一键安装程序 (Linux/macOS)"
echo "============================================================"
echo ""
echo "  此脚本将自动："
echo "  - 检测 Python 环境"
echo "  - 检测 NVIDIA GPU"
echo "  - 安装 PaddlePaddle (GPU/CPU 版本)"
echo "  - 安装 cuDNN 库 (如果使用 GPU)"
echo "  - 安装 PaddleOCR 及其他依赖"
echo ""

# 检测 Python
detect_python() {
    for cmd in python3 python; do
        if command -v $cmd &> /dev/null; then
            version=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            if [[ "$version" =~ ^3\.(9|10|11|12) ]]; then
                echo $cmd
                return
            fi
        fi
    done
    echo ""
}

PYTHON=$(detect_python)
if [ -z "$PYTHON" ]; then
    echo "[错误] 未找到 Python 3.9+！"
    echo ""
    echo "请先安装 Python："
    case "$(uname -s)" in
        Darwin*) echo "  brew install python@3.11" ;;
        Linux*)  echo "  sudo apt install python3.11 python3.11-venv python3-pip" ;;
    esac
    exit 1
fi

echo "检测到 Python: $($PYTHON --version)"
echo ""

# 运行 Python 安装脚本
$PYTHON install.py "$@"

if [ $? -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "  安装失败！"
    echo "============================================================"
    echo ""
    echo "  可能的解决方法："
    echo "  1. 确保 Python 版本为 3.9-3.12"
    echo "  2. 尝试使用 CPU 版本: ./install.sh --cpu"
    echo "  3. 检查网络连接"
    exit 1
fi

echo ""
echo "============================================================"
echo "  快速开始"
echo "============================================================"
echo ""
echo "  启动服务器："
echo "    $PYTHON server.py"
echo ""
echo "  然后打开浏览器访问："
echo "    http://127.0.0.1:5000"
echo ""
echo "  命令行参数："
echo "    --cpu    强制使用 CPU 版本"
echo "    --gpu    强制使用 GPU 版本"
