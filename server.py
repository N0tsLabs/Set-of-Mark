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

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# 延迟导入 PaddleOCR（首次加载较慢）
_ocr_instance = None

def get_ocr():
    """获取 PaddleOCR 实例（单例）"""
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        print("Loading PaddleOCR model...")
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            use_gpu=is_gpu_available(),
            lang='ch',
            show_log=False,
        )
        print("PaddleOCR loaded!")
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
            "POST /ocr": "OCR text recognition",
            "POST /som": "Generate SoM marked image",
            "GET /health": "Health check",
            "GET /info": "Service info",
        }
    })

@app.route('/ocr', methods=['POST'])
def ocr():
    """
    OCR 文字识别
    
    Request:
      - image: base64 encoded image, or
      - image_path: local file path, or
      - multipart form with 'file' field
    
    Response:
      {
        "success": true,
        "count": 10,
        "elements": [
          {"id": 0, "text": "...", "confidence": 0.99, "box": [x1,y1,x2,y2]},
          ...
        ]
      }
    """
    try:
        image_path = get_image_from_request(request)
        if not image_path:
            return jsonify({"success": False, "error": "No image provided"}), 400
        
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
        
        # 清理临时文件
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
    
    Request:
      - image: base64 encoded image, or
      - image_path: local file path, or
      - multipart form with 'file' field
      - detect_contours: bool (default true)
      - return_image: bool (default true, return base64 image)
    
    Response:
      {
        "success": true,
        "count": 10,
        "elements": [...],
        "marked_image": "base64..."  (if return_image=true)
      }
    """
    try:
        image_path = get_image_from_request(request)
        if not image_path:
            return jsonify({"success": False, "error": "No image provided"}), 400
        
        # 获取选项
        data = request.json or {}
        detect_contours = data.get('detect_contours', True)
        return_image = data.get('return_image', True)
        
        # 运行 OCR
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
        if detect_contours:
            ui_elements = detect_ui_contours(image_path)
            # 合并并重新编号
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
        if return_image:
            marked_image_path = tempfile.mktemp(suffix=".png")
            draw_som_marks(str(image_path), elements, marked_image_path)
            
            with open(marked_image_path, 'rb') as f:
                response["marked_image"] = base64.b64encode(f.read()).decode()
            
            os.unlink(marked_image_path)
        
        # 清理临时文件
        cleanup_temp_file(image_path)
        
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

def detect_ui_contours(image_path, min_area=500, max_area=50000):
    """检测 UI 轮廓"""
    import cv2
    import numpy as np
    
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    elements = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h if h > 0 else 0
            
            if 0.2 < aspect_ratio < 5 and w > 20 and h > 15:
                elements.append({
                    "id": 0,
                    "type": "contour",
                    "box": [x, y, x + w, y + h],
                })
    
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
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  OCR-SoM API Server")
    print("=" * 60)
    print(f"\n  Device: {'GPU' if is_gpu_available() else 'CPU'}")
    print(f"  Server: http://{args.host}:{args.port}")
    print("\n  Endpoints:")
    print("    POST /ocr  - OCR text recognition")
    print("    POST /som  - Generate SoM marked image")
    print("    GET /health - Health check")
    print("    GET /info   - Service info")
    print("\n" + "=" * 60)
    
    # 预加载模型
    print("\nPreloading model (first time may take a while)...")
    get_ocr()
    
    print(f"\nServer is running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.\n")
    
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
