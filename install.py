#!/usr/bin/env python3
"""
OCR-SoM 跨平台一键安装脚本

自动检测并安装：
- 操作系统 (Windows/Linux/macOS)
- GPU 环境 (NVIDIA CUDA)
- cuDNN 库（GPU 版本需要）
- PaddlePaddle + PaddleOCR

使用方法:
  python install.py          # 自动检测并安装
  python install.py --cpu    # 强制使用 CPU 版本
  python install.py --gpu    # 强制使用 GPU 版本
"""

import subprocess
import sys
import platform
import shutil
import os
import re

# 清华镜像源
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

def run(cmd, check=True, capture=True):
    """运行命令"""
    print(f"  $ {cmd}")
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"  错误: {result.stderr.strip()}")
            return False
        return True
    else:
        # 不捕获输出，直接显示
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0

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
        # 通过 nvidia-smi 获取 CUDA 版本
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            output = result.stdout
            # nvidia-smi 输出中包含 "CUDA Version: XX.X"
            match = re.search(r'CUDA Version:\s*(\d+)', output)
            if match:
                return match.group(1)
        
        # 方法2: 通过 nvcc 获取 CUDA 版本
        nvcc_result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if nvcc_result.returncode == 0:
            output = nvcc_result.stdout
            match = re.search(r'release (\d+)', output)
            if match:
                return match.group(1)
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
                    if "3.9" in version or "3.10" in version or "3.11" in version or "3.12" in version:
                        return cmd
            except:
                pass
    return None

def install_cudnn():
    """安装 cuDNN（GPU 版本需要）"""
    print("\n  正在安装 cuDNN 库...")
    
    # 安装 cuDNN 8.x（PaddlePaddle 需要）
    cmd = f"{sys.executable} -m pip install nvidia-cudnn-cu11==8.9.5.29 -i {MIRROR} -q"
    success = run(cmd)
    
    if not success:
        # 尝试其他版本
        cmd = f"{sys.executable} -m pip install nvidia-cudnn-cu11 -i {MIRROR} -q"
        success = run(cmd)
    
    return success

def install_paddlepaddle(use_gpu=False, cuda_version=None):
    """安装 PaddlePaddle"""
    os_type = detect_os()
    
    if use_gpu:
        # Windows 上使用通用 GPU 版本
        if os_type == "windows":
            package = "paddlepaddle-gpu==2.6.2"
        else:
            # Linux/macOS 上使用特定 CUDA 版本
            if cuda_version and int(cuda_version) >= 12:
                package = "paddlepaddle-gpu==2.6.2.post120"
            else:
                package = "paddlepaddle-gpu==2.6.2.post116"
        
        print(f"  正在安装 PaddlePaddle GPU 版本...")
        
        # 先安装 cuDNN
        if not install_cudnn():
            print("  警告: cuDNN 安装失败，可能影响 GPU 功能")
    else:
        package = "paddlepaddle==2.6.2"
        print("  正在安装 PaddlePaddle CPU 版本...")
    
    cmd = f"{sys.executable} -m pip install {package} -i {MIRROR} -q"
    success = run(cmd)
    
    # 如果 GPU 版本安装失败，自动回退到 CPU 版本
    if not success and use_gpu:
        print("\n  GPU 版本安装失败，正在回退到 CPU 版本...")
        package = "paddlepaddle==2.6.2"
        cmd = f"{sys.executable} -m pip install {package} -i {MIRROR} -q"
        return run(cmd), False  # 返回安装结果和是否使用GPU
    
    return success, use_gpu

def install_deps():
    """安装其他依赖"""
    packages = [
        "paddleocr==2.7.3",
        '"numpy<2"',
        "opencv-python-headless",
        "Pillow",
        "flask",
        "flask-cors",
    ]
    cmd = f"{sys.executable} -m pip install {' '.join(packages)} -i {MIRROR} -q"
    return run(cmd)

def setup_nvidia_paths():
    """配置所有 NVIDIA 库路径"""
    from pathlib import Path
    nvidia_libs = [
        "nvidia.cudnn",
        "nvidia.cublas", 
        "nvidia.cuda_nvrtc",
    ]
    
    for module_name in nvidia_libs:
        try:
            module = __import__(module_name, fromlist=[''])
            lib_bin = Path(module.__path__[0]) / "bin"
            if lib_bin.exists():
                lib_bin_str = str(lib_bin)
                if lib_bin_str not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = lib_bin_str + os.pathsep + os.environ.get("PATH", "")
                    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(lib_bin_str)
        except ImportError:
            pass

def verify_gpu():
    """验证 GPU 是否真正可用"""
    try:
        # 设置所有 NVIDIA 库路径
        setup_nvidia_paths()
        
        import paddle
        if paddle.is_compiled_with_cuda():
            # 尝试实际使用 GPU
            try:
                paddle.device.set_device('gpu:0')
                x = paddle.to_tensor([1.0])
                _ = x + x
                return True
            except Exception as e:
                print(f"  GPU 测试失败: {e}")
                return False
        return False
    except Exception as e:
        print(f"  GPU 验证失败: {e}")
        return False

def main():
    print("=" * 60)
    print("  OCR-SoM 一键安装程序")
    print("=" * 60)
    
    # 解析参数
    force_cpu = "--cpu" in sys.argv
    force_gpu = "--gpu" in sys.argv
    
    # 1. 检测环境
    print("\n[1/5] 正在检测环境...")
    
    os_type = detect_os()
    print(f"  操作系统: {os_type}")
    
    python_cmd = get_python_cmd()
    if not python_cmd:
        print("  错误: 未找到 Python 3.9-3.12！")
        print("  请先安装 Python: https://www.python.org/downloads/")
        sys.exit(1)
    print(f"  Python 版本: {sys.version.split()[0]}")
    
    gpus = detect_gpu()
    cuda_version = detect_cuda_version() if gpus else None
    
    if gpus:
        print(f"  显卡: {gpus[0]}")
        if cuda_version:
            print(f"  CUDA 版本: {cuda_version}")
    else:
        print("  显卡: 未检测到 NVIDIA GPU")
    
    # 2. 决定安装版本
    print("\n[2/5] 正在确定安装类型...")
    
    use_gpu = False
    if force_cpu:
        print("  模式: CPU（通过 --cpu 参数强制指定）")
    elif force_gpu:
        if gpus:
            use_gpu = True
            print(f"  模式: GPU（通过 --gpu 参数强制指定）")
        else:
            print("  警告: 指定了 --gpu 但未检测到 GPU，将使用 CPU 版本")
    elif gpus and cuda_version:
        use_gpu = True
        print(f"  模式: GPU（自动检测）")
        print(f"  说明: 将自动安装 cuDNN 库（约 700MB）")
    else:
        print("  模式: CPU（未检测到 GPU）")
    
    # 3. 安装 PaddlePaddle
    print("\n[3/5] 正在安装 PaddlePaddle...")
    success, actual_gpu = install_paddlepaddle(use_gpu, cuda_version)
    if not success:
        print("  PaddlePaddle 安装失败！")
        sys.exit(1)
    
    # 4. 安装其他依赖
    print("\n[4/5] 正在安装其他依赖...")
    if not install_deps():
        print("  依赖安装失败！")
        sys.exit(1)
    
    # 5. 验证安装
    print("\n[5/5] 正在验证安装...")
    
    # 重新加载模块
    if 'paddle' in sys.modules:
        del sys.modules['paddle']
    
    try:
        # 设置所有 NVIDIA 库路径
        setup_nvidia_paths()
        
        # 显示配置的路径
        from pathlib import Path
        for lib_name, module_name in [("cuDNN", "nvidia.cudnn"), ("cuBLAS", "nvidia.cublas"), ("NVRTC", "nvidia.cuda_nvrtc")]:
            try:
                module = __import__(module_name, fromlist=[''])
                lib_bin = Path(module.__path__[0]) / "bin"
                if lib_bin.exists():
                    print(f"  {lib_name} 路径: {lib_bin}")
            except ImportError:
                pass
        
        import paddle
        gpu_available = paddle.is_compiled_with_cuda()
        device = "GPU" if gpu_available and actual_gpu else "CPU"
        print(f"  PaddlePaddle 版本: {paddle.__version__} ({device})")
        
        # 如果是 GPU 版本，验证是否真正可用
        if actual_gpu and gpu_available:
            if verify_gpu():
                print("  GPU 加速: 已验证可用")
            else:
                print("  GPU 加速: 验证失败，将使用 CPU")
                device = "CPU"
        
    except ImportError as e:
        print(f"  警告: {e}")
        device = "CPU"
    
    try:
        from paddleocr import PaddleOCR
        print("  PaddleOCR: 正常")
    except ImportError as e:
        print(f"  警告: {e}")
    
    print("\n" + "=" * 60)
    print("  安装完成！")
    print("=" * 60)
    print(f"\n  运行模式: {device}")
    print("\n  使用方法：")
    print("    python ocr_som.py <图片路径>          # 命令行模式")
    print("    python server.py                      # 启动 API 服务器")
    print("    python server.py --port 8080         # 自定义端口")
    print("\n  打开浏览器访问 http://127.0.0.1:5000 即可使用网页界面")

if __name__ == "__main__":
    main()
