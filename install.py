#!/usr/bin/env python3
"""
OCR-SoM 跨平台一键安装脚本

自动检测：
- 操作系统 (Windows/Linux/macOS)
- GPU 环境 (NVIDIA CUDA)
- Python 版本

Usage:
  python install.py          # 自动检测并安装
  python install.py --cpu    # 强制使用 CPU 版本
  python install.py --gpu    # 强制使用 GPU 版本
"""

import subprocess
import sys
import platform
import shutil
import os

# 清华镜像源
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

def run(cmd, check=True):
    """运行命令"""
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  Error: {result.stderr}")
        return False
    return True

def detect_os():
    """检测操作系统"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system  # windows, linux

def detect_gpu():
    """检测 NVIDIA GPU"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            gpus = result.stdout.strip().split('\n')
            return gpus
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None

def detect_cuda_version():
    """检测 CUDA 版本"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # 通过 nvcc 获取 CUDA 版本
            nvcc_result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if nvcc_result.returncode == 0:
                output = nvcc_result.stdout
                if "release 12" in output:
                    return "12"
                elif "release 11" in output:
                    return "11"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None

def get_python_cmd():
    """获取 Python 命令"""
    for cmd in ["python3", "python", "py"]:
        if shutil.which(cmd):
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    if "3.9" in version or "3.10" in version or "3.11" in version:
                        return cmd
            except:
                pass
    return None

def install_paddlepaddle(use_gpu=None, cuda_version=None):
    """安装 PaddlePaddle"""
    os_type = detect_os()
    
    if use_gpu and cuda_version:
        if cuda_version == "12":
            package = "paddlepaddle-gpu==2.6.2.post120"
        else:
            package = "paddlepaddle-gpu==2.6.2.post116"
        print(f"  Installing GPU version (CUDA {cuda_version})...")
    else:
        package = "paddlepaddle==2.6.2"
        print("  Installing CPU version...")
    
    cmd = f"{sys.executable} -m pip install {package} -i {MIRROR}"
    return run(cmd)

def install_deps():
    """安装其他依赖"""
    packages = [
        "paddleocr==2.7.3",
        "numpy<2",
        "opencv-python-headless",
        "Pillow",
        "flask",
        "flask-cors",
    ]
    cmd = f"{sys.executable} -m pip install {' '.join(packages)} -i {MIRROR}"
    return run(cmd)

def main():
    print("=" * 60)
    print("  OCR-SoM Installer")
    print("=" * 60)
    
    # 解析参数
    force_cpu = "--cpu" in sys.argv
    force_gpu = "--gpu" in sys.argv
    
    # 1. 检测环境
    print("\n[1/4] Detecting environment...")
    
    os_type = detect_os()
    print(f"  OS: {os_type}")
    
    python_cmd = get_python_cmd()
    if not python_cmd:
        print("  Error: Python 3.9-3.11 not found!")
        print("  Please install Python first: https://www.python.org/downloads/")
        sys.exit(1)
    print(f"  Python: {sys.version.split()[0]}")
    
    gpus = detect_gpu()
    cuda_version = detect_cuda_version() if gpus else None
    
    if gpus:
        print(f"  GPU: {gpus[0]}")
        if cuda_version:
            print(f"  CUDA: {cuda_version}")
    else:
        print("  GPU: Not found (will use CPU)")
    
    # 2. 决定安装版本
    print("\n[2/4] Determining installation type...")
    
    use_gpu = False
    if force_cpu:
        print("  Mode: CPU (forced by --cpu)")
    elif force_gpu:
        if gpus and cuda_version:
            use_gpu = True
            print(f"  Mode: GPU (CUDA {cuda_version})")
        else:
            print("  Warning: --gpu specified but no CUDA found, falling back to CPU")
    elif gpus and cuda_version:
        use_gpu = True
        print(f"  Mode: GPU (auto-detected CUDA {cuda_version})")
    else:
        print("  Mode: CPU (no GPU detected)")
    
    # 3. 安装 PaddlePaddle
    print("\n[3/4] Installing PaddlePaddle...")
    if not install_paddlepaddle(use_gpu, cuda_version):
        print("  Failed to install PaddlePaddle!")
        sys.exit(1)
    
    # 4. 安装其他依赖
    print("\n[4/4] Installing dependencies...")
    if not install_deps():
        print("  Failed to install dependencies!")
        sys.exit(1)
    
    # 5. 验证安装
    print("\n" + "=" * 60)
    print("  Verifying installation...")
    try:
        import paddle
        device = "GPU" if paddle.is_compiled_with_cuda() and use_gpu else "CPU"
        print(f"  PaddlePaddle: {paddle.__version__} ({device})")
    except ImportError as e:
        print(f"  Warning: {e}")
    
    try:
        from paddleocr import PaddleOCR
        print("  PaddleOCR: OK")
    except ImportError as e:
        print(f"  Warning: {e}")
    
    print("\n" + "=" * 60)
    print("  Installation complete!")
    print("=" * 60)
    print("\nUsage:")
    print("  python ocr_som.py <image>           # CLI mode")
    print("  python server.py                     # Start API server")
    print("  python server.py --port 8080        # Custom port")

if __name__ == "__main__":
    main()
