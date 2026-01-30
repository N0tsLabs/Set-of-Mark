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

from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS

# 网页界面 HTML
WEB_UI_HTML = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR-SoM 测试</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: white; text-align: center; margin-bottom: 20px; font-size: 2em; }
        .card { 
            background: white; border-radius: 16px; padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2); margin-bottom: 20px;
        }
        .upload-area {
            border: 3px dashed #ddd; border-radius: 12px; padding: 40px;
            text-align: center; cursor: pointer; transition: all 0.3s;
        }
        .upload-area:hover { border-color: #667eea; background: #f8f9ff; }
        .upload-area.dragover { border-color: #667eea; background: #f0f2ff; }
        .upload-icon { font-size: 48px; margin-bottom: 10px; }
        .upload-text { color: #666; font-size: 16px; }
        .upload-hint { color: #999; font-size: 13px; margin-top: 8px; }
        input[type="file"] { display: none; }
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white; border: none; padding: 12px 32px; border-radius: 8px;
            font-size: 16px; cursor: pointer; transition: transform 0.2s;
        }
        .btn:hover { transform: scale(1.05); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .preview-container { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 20px; }
        .preview-box { flex: 1; min-width: 300px; }
        .preview-box h3 { margin-bottom: 12px; color: #333; font-size: 16px; }
        .preview-img { 
            width: 100%; border-radius: 8px; border: 1px solid #eee;
            max-height: 500px; object-fit: contain; background: #f5f5f5;
        }
        .result-panel { margin-top: 20px; }
        .result-panel h3 { margin-bottom: 12px; color: #333; }
        .result-stats { 
            display: flex; gap: 20px; margin-bottom: 16px; flex-wrap: wrap;
        }
        .stat-item {
            background: #f8f9ff; padding: 12px 20px; border-radius: 8px;
            text-align: center;
        }
        .stat-value { font-size: 24px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 12px; color: #666; margin-top: 4px; }
        .elements-list {
            max-height: 300px; overflow-y: auto; border: 1px solid #eee;
            border-radius: 8px; font-family: monospace; font-size: 13px;
        }
        .element-item {
            padding: 8px 12px; border-bottom: 1px solid #f0f0f0;
            display: flex; align-items: center; gap: 12px;
        }
        .element-item:last-child { border-bottom: none; }
        .element-id {
            background: #667eea; color: white; padding: 2px 8px;
            border-radius: 4px; font-weight: bold; min-width: 30px; text-align: center;
        }
        .element-text { flex: 1; color: #333; }
        .element-box { color: #999; font-size: 12px; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .spinner {
            width: 40px; height: 40px; border: 4px solid #f0f0f0;
            border-top-color: #667eea; border-radius: 50%;
            animation: spin 1s linear infinite; margin: 0 auto 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .hidden { display: none; }
        .error { color: #e74c3c; text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 OCR-SoM 测试工具</h1>
        
        <div class="card">
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📷</div>
                <div class="upload-text">点击或拖拽上传截图</div>
                <div class="upload-hint">支持 PNG、JPG、GIF 格式</div>
            </div>
            <input type="file" id="fileInput" accept="image/*">
            
            <div class="preview-container hidden" id="previewContainer">
                <div class="preview-box">
                    <h3>原图</h3>
                    <img id="originalImg" class="preview-img">
                </div>
                <div class="preview-box">
                    <h3>标注结果</h3>
                    <img id="markedImg" class="preview-img">
                </div>
            </div>
            
            <div class="loading hidden" id="loading">
                <div class="spinner"></div>
                <div>正在识别中...</div>
            </div>
            
            <div class="error hidden" id="error"></div>
            
            <div class="result-panel hidden" id="resultPanel">
                <h3>识别结果</h3>
                <div class="result-stats" id="resultStats"></div>
                <div class="elements-list" id="elementsList"></div>
            </div>
        </div>
    </div>
    
    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const previewContainer = document.getElementById('previewContainer');
        const originalImg = document.getElementById('originalImg');
        const markedImg = document.getElementById('markedImg');
        const loading = document.getElementById('loading');
        const errorDiv = document.getElementById('error');
        const resultPanel = document.getElementById('resultPanel');
        const resultStats = document.getElementById('resultStats');
        const elementsList = document.getElementById('elementsList');
        
        // 点击上传
        uploadArea.addEventListener('click', () => fileInput.click());
        
        // 拖拽上传
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        
        // 文件选择
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                handleFile(fileInput.files[0]);
            }
        });
        
        async function handleFile(file) {
            if (!file.type.startsWith('image/')) {
                showError('请上传图片文件');
                return;
            }
            
            // 显示原图预览
            const reader = new FileReader();
            reader.onload = (e) => {
                originalImg.src = e.target.result;
                previewContainer.classList.remove('hidden');
                markedImg.src = '';
            };
            reader.readAsDataURL(file);
            
            // 调用 API
            loading.classList.remove('hidden');
            errorDiv.classList.add('hidden');
            resultPanel.classList.add('hidden');
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch('/som', {
                    method: 'POST',
                    body: formData
                });
                
                // 重新发送带 JSON 的请求以获取 return_image
                const base64 = await fileToBase64(file);
                const jsonResponse = await fetch('/som', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: base64, return_image: true })
                });
                
                const data = await jsonResponse.json();
                
                if (data.success) {
                    showResult(data);
                } else {
                    showError(data.error || '识别失败');
                }
            } catch (err) {
                showError('请求失败: ' + err.message);
            } finally {
                loading.classList.add('hidden');
            }
        }
        
        function fileToBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }
        
        function showResult(data) {
            // 显示标注图
            if (data.marked_image) {
                markedImg.src = 'data:image/png;base64,' + data.marked_image;
            }
            
            // 统计
            const textCount = data.elements.filter(e => e.type === 'text').length;
            const contourCount = data.elements.filter(e => e.type === 'contour').length;
            
            resultStats.innerHTML = `
                <div class="stat-item">
                    <div class="stat-value">${data.count}</div>
                    <div class="stat-label">总元素数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${textCount}</div>
                    <div class="stat-label">文字元素</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${contourCount}</div>
                    <div class="stat-label">UI 轮廓</div>
                </div>
            `;
            
            // 元素列表
            elementsList.innerHTML = data.elements.map(el => `
                <div class="element-item">
                    <span class="element-id">${el.id}</span>
                    <span class="element-text">${el.text || '[UI 元素]'}</span>
                    <span class="element-box">[${el.box.join(', ')}]</span>
                </div>
            `).join('');
            
            resultPanel.classList.remove('hidden');
        }
        
        function showError(msg) {
            errorDiv.textContent = msg;
            errorDiv.classList.remove('hidden');
        }
    </script>
</body>
</html>
'''

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

@app.route('/', methods=['GET'])
def index():
    """网页测试界面"""
    return render_template_string(WEB_UI_HTML)

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
    print(f"\n  Web UI: http://{args.host}:{args.port}/")
    print("\n  API Endpoints:")
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
