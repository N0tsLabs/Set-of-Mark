#!/usr/bin/env python3
"""
OCR-SoM HTTP API Server

提供本地 HTTP API 供其他程序调用。

Usage:
  python server.py                  # 默认端口 5000
  python server.py --port 8080      # 自定义端口
  python server.py --host 0.0.0.0   # 允许外部访问

API:
  POST /ocr          - 识别图片中的文字
  POST /som          - 生成 SoM 标注图
  GET  /health       - 健康检查
  GET  /info         - 服务信息
"""

import os
import sys
import json
import base64
import argparse
import tempfile
from io import BytesIO
from pathlib import Path

# 设置环境变量
os.environ["CUDA_VISIBLE_DEVICES"] = os.environ.get("CUDA_VISIBLE_DEVICES", "")
os.environ["FLAGS_use_mkldnn"] = "0"

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

# 获取项目目录
PROJECT_DIR = Path(__file__).parent
WEB_DIR = PROJECT_DIR / "web"
MODELS_DIR = PROJECT_DIR / "models"

# 确保模型目录存在
MODELS_DIR.mkdir(exist_ok=True)

# 延迟导入 PaddleOCR（首次加载较慢）
_ocr_instance = None

def get_ocr():
    """获取 PaddleOCR 实例（单例），模型保存到项目目录"""
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        print("正在加载 PaddleOCR 模型...")
        print(f"模型目录: {MODELS_DIR}")
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            use_gpu=is_gpu_available(),
            lang='ch',
            show_log=False,
            det_model_dir=str(MODELS_DIR / "det"),
            rec_model_dir=str(MODELS_DIR / "rec"),
            cls_model_dir=str(MODELS_DIR / "cls"),
        )
        print("PaddleOCR 加载完成!")
    return _ocr_instance

def is_gpu_available():
    """检查 GPU 是否可用"""
    try:
        import paddle
        return paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
    except:
        return False

app = Flask(__name__)
CORS(app)  # 允许跨域请求

@app.route('/', methods=['GET'])
def index():
    """网页测试界面"""
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})

@app.route('/info', methods=['GET'])
def info():
    """服务信息"""
    gpu_available = is_gpu_available()
    return jsonify({
        "name": "OCR-SoM",
        "version": "1.0.0",
        "device": "GPU" if gpu_available else "CPU",
        "endpoints": {
            "POST /ocr": "OCR 文字识别",
            "POST /som": "生成 SoM 标注图",
            "GET /health": "健康检查",
            "GET /info": "服务信息",
        }
    })

@app.route('/ocr', methods=['POST'])
def ocr():
    """OCR 文字识别"""
    try:
        image_path = get_image_from_request(request)
        if not image_path:
            return jsonify({"success": False, "error": "未提供图片"}), 400
        
        ocr_instance = get_ocr()
        result = ocr_instance.ocr(str(image_path), cls=True)
        
        elements = []
        if result and result[0]:
            for i, line in enumerate(result[0]):
                box = line[0]
                text = line[1][0]
                confidence = line[1][1]
                
                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]
                x1, y1 = min(x_coords), min(y_coords)
                x2, y2 = max(x_coords), max(y_coords)
                
                elements.append({
                    "id": i,
                    "type": "text",
                    "text": text,
                    "confidence": round(float(confidence), 4),
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                    "polygon": [[int(p[0]), int(p[1])] for p in box],
                })
        
        cleanup_temp_file(image_path)
        
        return jsonify({
            "success": True,
            "count": len(elements),
            "elements": elements,
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/som', methods=['POST'])
def som():
    """
    生成 SoM 标注图
    
    参数:
      - detect_contours: bool (默认 true) - 是否检测 UI 轮廓
      - return_image: bool (默认 true) - 是否返回标注图
      - min_area: int (默认 200) - 轮廓最小面积
      - max_area: int (默认 80000) - 轮廓最大面积
      - min_size: int (默认 16) - 轮廓最小尺寸
      - fill_ratio: float (默认 0.3) - 轮廓填充率阈值
      - saturation_threshold: int (默认 40) - 彩色图标饱和度阈值
      - ocr_only: bool (默认 false) - 仅 OCR，不检测轮廓（快速模式）
    """
    try:
        image_path = get_image_from_request(request)
        if not image_path:
            return jsonify({"success": False, "error": "未提供图片"}), 400
        
        # 获取选项（兼容 multipart form 和 json）
        options = {
            'detect_contours': True,
            'return_image': True,
            'min_area': 200,
            'max_area': 80000,
            'min_size': 16,
            'fill_ratio': 0.3,
            'saturation_threshold': 40,
            'ocr_only': False,
        }
        
        if request.is_json:
            data = request.json or {}
            for key in options:
                if key in data:
                    options[key] = data[key]
        
        # ocr_only 模式下禁用轮廓检测
        if options['ocr_only']:
            options['detect_contours'] = False
        
        # 运行 OCR
        import time
        start_time = time.time()
        print(f"\n[请求] /som - 开始处理图片...")
        print(f"  参数: ocr_only={options['ocr_only']}, detect_contours={options['detect_contours']}")
        if options['detect_contours']:
            print(f"  轮廓: min_area={options['min_area']}, max_area={options['max_area']}, min_size={options['min_size']}")
        
        ocr_instance = get_ocr()
        result = ocr_instance.ocr(str(image_path), cls=True)
        
        elements = []
        if result and result[0]:
            for i, line in enumerate(result[0]):
                box = line[0]
                text = line[1][0]
                confidence = line[1][1]
                
                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]
                x1, y1 = min(x_coords), min(y_coords)
                x2, y2 = max(x_coords), max(y_coords)
                
                elements.append({
                    "id": i,
                    "type": "text",
                    "text": text,
                    "confidence": round(float(confidence), 4),
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                })
        
        # 检测 UI 轮廓
        if options['detect_contours']:
            ui_elements = detect_ui_contours(
                image_path,
                min_area=options['min_area'],
                max_area=options['max_area'],
                min_size=options['min_size'],
                fill_ratio=options['fill_ratio'],
                saturation_threshold=options['saturation_threshold'],
            )
            start_id = len(elements)
            for i, el in enumerate(ui_elements):
                el["id"] = start_id + i
                elements.append(el)
        
        response = {
            "success": True,
            "count": len(elements),
            "elements": elements,
        }
        
        # 生成标注图
        if options['return_image']:
            marked_image_path = tempfile.mktemp(suffix=".png")
            draw_som_marks(str(image_path), elements, marked_image_path)
            
            with open(marked_image_path, 'rb') as f:
                response["marked_image"] = base64.b64encode(f.read()).decode()
            
            os.unlink(marked_image_path)
        
        cleanup_temp_file(image_path)
        
        elapsed = time.time() - start_time
        text_count = sum(1 for el in elements if el.get('type') == 'text')
        ui_count = sum(1 for el in elements if el.get('type') == 'ui')
        print(f"  完成! 耗时 {elapsed:.2f}s, 识别 {text_count} 个文字, {ui_count} 个UI元素")
        
        return jsonify(response)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

def get_image_from_request(req):
    """从请求中获取图片"""
    # 1. multipart form
    if 'file' in req.files:
        file = req.files['file']
        temp_path = tempfile.mktemp(suffix=".png")
        file.save(temp_path)
        return temp_path
    
    # 2. JSON body
    if req.is_json:
        data = req.json or {}
        
        # 2.1 base64 image
        if 'image' in data:
            image_data = base64.b64decode(data['image'])
            temp_path = tempfile.mktemp(suffix=".png")
            with open(temp_path, 'wb') as f:
                f.write(image_data)
            return temp_path
        
        # 2.2 local file path
        if 'image_path' in data:
            path = data['image_path']
            if os.path.exists(path):
                return path
    
    return None

def cleanup_temp_file(path):
    """清理临时文件"""
    if path and tempfile.gettempdir() in str(path):
        try:
            os.unlink(path)
        except:
            pass

def detect_ui_contours(image_path, min_area=200, max_area=80000, min_size=16, fill_ratio=0.3, saturation_threshold=40):
    """
    检测 UI 轮廓
    
    参数:
      - min_area: 最小面积
      - max_area: 最大面积
      - min_size: 最小尺寸 (宽和高)
      - fill_ratio: 填充率阈值 (轮廓面积/矩形面积)
      - saturation_threshold: 彩色图标饱和度阈值
    """
    import cv2
    import numpy as np
    
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    
    img_h, img_w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elements = []
    seen_boxes = []
    
    def is_duplicate(x, y, w, h):
        """检查是否重复（IoU > 0.5 视为重复）"""
        for (sx, sy, sw, sh) in seen_boxes:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + w, sx + sw), min(y + h, sy + sh)
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                union = w * h + sw * sh - inter
                if inter / union > 0.5:
                    return True
        return False
    
    def add_element(x, y, w, h):
        """添加元素"""
        if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
            return
        if w < min_size or h < min_size or w * h < min_area or w * h > max_area:
            return
        aspect = w / h if h > 0 else 0
        if aspect < 0.15 or aspect > 7:
            return
        if is_duplicate(x, y, w, h):
            return
        seen_boxes.append((x, y, w, h))
        elements.append({
            "id": 0,
            "type": "contour",
            "box": [int(x), int(y), int(x + w), int(y + h)],
        })
    
    # 方法 1: Canny 边缘检测
    for low, high in [(30, 100), (50, 150)]:
        edges = cv2.Canny(gray, low, high)
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(cnt)
                rect_area = w * h
                ratio = area / rect_area if rect_area > 0 else 0
                if ratio > fill_ratio:
                    add_element(x, y, w, h)
    
    # 方法 2: 检测高饱和度区域（彩色图标）
    if saturation_threshold > 0:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        _, sat_mask = cv2.threshold(saturation, saturation_threshold, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        sat_mask = cv2.morphologyEx(sat_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(cnt)
                add_element(x, y, w, h)
    
    return elements

def draw_som_marks(image_path, elements, output_path):
    """绘制 SoM 标注"""
    import cv2
    import numpy as np
    
    img = cv2.imread(str(image_path))
    if img is None:
        return
    
    # 颜色列表
    colors = [
        (255, 107, 107), (78, 205, 196), (255, 230, 109),
        (199, 125, 255), (107, 185, 240), (255, 179, 71),
        (162, 217, 206), (255, 154, 162), (181, 234, 215),
        (255, 218, 185),
    ]
    
    for el in elements:
        color = colors[el["id"] % len(colors)]
        x1, y1, x2, y2 = el["box"]
        
        # 画框
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        
        # 画编号标签
        label = str(el["id"])
        font_scale = 0.5
        thickness = 1
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        
        # 标签背景
        cv2.rectangle(img, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
        # 标签文字
        cv2.putText(img, label, (x1 + 3, y1 - 3), cv2.FONT_HERSHEY_SIMPLEX, 
                    font_scale, (255, 255, 255), thickness)
    
    cv2.imwrite(output_path, img)

def main():
    parser = argparse.ArgumentParser(description="OCR-SoM API Server")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="端口 (默认: 5000)")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  OCR-SoM API 服务")
    print("=" * 60)
    print(f"\n  设备: {'GPU' if is_gpu_available() else 'CPU'}")
    print(f"  地址: http://{args.host}:{args.port}")
    print(f"\n  网页界面: http://{args.host}:{args.port}/")
    print("\n  API 接口:")
    print("    POST /ocr  - OCR 文字识别")
    print("    POST /som  - 生成 SoM 标注图")
    print("    GET /health - 健康检查")
    print("    GET /info   - 服务信息")
    print("\n" + "=" * 60)
    
    # 预加载模型
    print("\n正在预加载模型（首次加载可能较慢）...")
    get_ocr()
    
    print(f"\n服务已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务\n")
    
    # 禁用 Flask/Werkzeug 默认日志
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
