#!/bin/bash
#
# OCR-SoM 跨平台一键安装脚本 (Linux/macOS)
#
# Usage:
#   chmod +x install.sh
#   ./install.sh          # 自动检测并安装
#   ./install.sh --cpu    # 强制使用 CPU 版本
#   ./install.sh --gpu    # 强制使用 GPU 版本
#

set -e

MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

echo "============================================================"
echo "  OCR-SoM Installer"
echo "============================================================"

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos" ;;
        Linux*)  echo "linux" ;;
        *)       echo "unknown" ;;
    esac
}

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

# 检测 NVIDIA GPU
detect_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1
    else
        echo ""
    fi
}

# 检测 CUDA 版本
detect_cuda() {
    if command -v nvcc &> /dev/null; then
        nvcc --version 2>/dev/null | grep -oE "release [0-9]+" | grep -oE "[0-9]+"
    else
        echo ""
    fi
}

# 1. 检测环境
echo ""
echo "[1/4] Detecting environment..."

OS=$(detect_os)
echo "  OS: $OS"

PYTHON=$(detect_python)
if [ -z "$PYTHON" ]; then
    echo "  Error: Python 3.9+ not found!"
    echo "  Please install Python first:"
    if [ "$OS" = "macos" ]; then
        echo "    brew install python@3.11"
    else
        echo "    sudo apt install python3.11 python3.11-venv python3-pip"
    fi
    exit 1
fi
echo "  Python: $($PYTHON --version)"

GPU=$(detect_gpu)
CUDA=$(detect_cuda)
if [ -n "$GPU" ]; then
    echo "  GPU: $GPU"
    if [ -n "$CUDA" ]; then
        echo "  CUDA: $CUDA"
    fi
else
    echo "  GPU: Not found (will use CPU)"
fi

# 2. 决定安装版本
echo ""
echo "[2/4] Determining installation type..."

USE_GPU=false
CUDA_VER=""

if [[ "$1" == "--cpu" ]]; then
    echo "  Mode: CPU (forced by --cpu)"
elif [[ "$1" == "--gpu" ]]; then
    if [ -n "$GPU" ] && [ -n "$CUDA" ]; then
        USE_GPU=true
        CUDA_VER=$CUDA
        echo "  Mode: GPU (CUDA $CUDA_VER)"
    else
        echo "  Warning: --gpu specified but no CUDA found, falling back to CPU"
    fi
elif [ -n "$GPU" ] && [ -n "$CUDA" ]; then
    USE_GPU=true
    CUDA_VER=$CUDA
    echo "  Mode: GPU (auto-detected CUDA $CUDA_VER)"
else
    echo "  Mode: CPU (no GPU detected)"
fi

# 3. 安装 PaddlePaddle
echo ""
echo "[3/4] Installing PaddlePaddle..."

if [ "$USE_GPU" = true ]; then
    if [ "$CUDA_VER" = "12" ]; then
        PADDLE_PKG="paddlepaddle-gpu==2.6.2.post120"
    else
        PADDLE_PKG="paddlepaddle-gpu==2.6.2.post116"
    fi
    echo "  Installing GPU version (CUDA $CUDA_VER)..."
else
    PADDLE_PKG="paddlepaddle==2.6.2"
    echo "  Installing CPU version..."
fi

$PYTHON -m pip install $PADDLE_PKG -i $MIRROR -q

# 4. 安装其他依赖
echo ""
echo "[4/4] Installing dependencies..."

$PYTHON -m pip install \
    paddleocr==2.7.3 \
    "numpy<2" \
    opencv-python-headless \
    Pillow \
    flask \
    flask-cors \
    -i $MIRROR -q

# 验证安装
echo ""
echo "============================================================"
echo "  Verifying installation..."

$PYTHON -c "import paddle; print(f'  PaddlePaddle: {paddle.__version__}')" 2>/dev/null || true
$PYTHON -c "from paddleocr import PaddleOCR; print('  PaddleOCR: OK')" 2>/dev/null || true

echo ""
echo "============================================================"
echo "  Installation complete!"
echo "============================================================"
echo ""
echo "Usage:"
echo "  $PYTHON ocr_som.py <image>        # CLI mode"
echo "  $PYTHON server.py                  # Start API server"
echo "  $PYTHON server.py --port 8080     # Custom port"
