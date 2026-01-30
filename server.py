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

# 网页界面 HTML - 白色简约主题
WEB_UI_HTML = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OCR-SoM</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
        }
        .header {
            background: white;
            border-bottom: 1px solid #e0e0e0;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 { font-size: 18px; font-weight: 600; color: #333; }
        .header .status { font-size: 13px; color: #666; }
        .main { padding: 24px; max-width: 1400px; margin: 0 auto; }
        
        /* 上传区域 */
        .upload-section { text-align: center; padding: 60px 20px; }
        .upload-section.has-result { padding: 20px; }
        .upload-btn {
            background: #333;
            color: white;
            border: none;
            padding: 14px 36px;
            border-radius: 8px;
            font-size: 15px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .upload-btn:hover { background: #555; }
        .upload-hint { color: #999; font-size: 13px; margin-top: 12px; }
        input[type="file"] { display: none; }
        
        /* 结果区域 */
        .result-section { display: none; }
        .result-section.show { display: block; }
        
        /* 图片查看器 */
        .viewer {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
            margin-bottom: 20px;
        }
        .viewer-header {
            padding: 12px 16px;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .viewer-title { font-size: 14px; font-weight: 500; color: #333; }
        .viewer-stats { font-size: 13px; color: #666; }
        .viewer-body {
            padding: 16px;
            background: #fafafa;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 300px;
        }
        .viewer-img {
            max-width: 100%;
            max-height: 70vh;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        /* 文字结果 */
        .text-result {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }
        .text-result-header {
            padding: 12px 16px;
            border-bottom: 1px solid #eee;
            font-size: 14px;
            font-weight: 500;
            color: #333;
        }
        .text-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .text-item {
            padding: 10px 16px;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
        }
        .text-item:last-child { border-bottom: none; }
        .text-item:hover { background: #f9f9f9; }
        .text-id {
            background: #333;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            min-width: 28px;
            text-align: center;
        }
        .text-content { flex: 1; color: #333; }
        .text-coords { color: #999; font-size: 12px; font-family: monospace; }
        
        /* 加载状态 */
        .loading {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid #eee;
            border-top-color: #333;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .error {
            text-align: center;
            padding: 20px;
            color: #e53935;
            font-size: 14px;
        }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="header">
        <h1>OCR-SoM</h1>
        <span class="status" id="deviceStatus"></span>
    </div>
    
    <div class="main">
        <div class="upload-section" id="uploadSection">
            <button class="upload-btn" id="uploadBtn">选择图片</button>
            <p class="upload-hint">支持 PNG、JPG、GIF 格式，点击或拖拽上传</p>
        </div>
        <input type="file" id="fileInput" accept="image/*">
        
        <div class="loading hidden" id="loading">
            <div class="spinner"></div>
            <div>识别中...</div>
        </div>
        
        <div class="error hidden" id="error"></div>
        
        <div class="result-section" id="resultSection">
            <div class="viewer">
                <div class="viewer-header">
                    <span class="viewer-title">标注结果</span>
                    <span class="viewer-stats" id="stats"></span>
                </div>
                <div class="viewer-body">
                    <img id="resultImg" class="viewer-img">
                </div>
            </div>
            
            <div class="text-result">
                <div class="text-result-header">识别文字</div>
                <div class="text-list" id="textList"></div>
            </div>
        </div>
    </div>
    
    <script>
        const uploadSection = document.getElementById('uploadSection');
        const uploadBtn = document.getElementById('uploadBtn');
        const fileInput = document.getElementById('fileInput');
        const loading = document.getElementById('loading');
        const errorDiv = document.getElementById('error');
        const resultSection = document.getElementById('resultSection');
        const resultImg = document.getElementById('resultImg');
        const stats = document.getElementById('stats');
        const textList = document.getElementById('textList');
        const deviceStatus = document.getElementById('deviceStatus');
        
        // 获取设备信息
        fetch('/info').then(r => r.json()).then(data => {
            deviceStatus.textContent = data.device;
        });
        
        // 点击上传
        uploadBtn.addEventListener('click', () => fileInput.click());
        
        // 拖拽上传
        document.body.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadSection.style.background = '#f0f0f0';
        });
        document.body.addEventListener('dragleave', () => {
            uploadSection.style.background = '';
        });
        document.body.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadSection.style.background = '';
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
            
            // 显示加载
            loading.classList.remove('hidden');
            errorDiv.classList.add('hidden');
            resultSection.classList.remove('show');
            uploadSection.classList.add('has-result');
            
            try {
                const base64 = await fileToBase64(file);
                const response = await fetch('/som', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: base64, return_image: true })
                });
                
                const data = await response.json();
                
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
                resultImg.src = 'data:image/png;base64,' + data.marked_image;
            }
            
            // 统计
            const textCount = data.elements.filter(e => e.type === 'text').length;
            stats.textContent = `共 ${data.count} 个元素，${textCount} 个文字`;
            
            // 文字列表
            const textElements = data.elements.filter(e => e.type === 'text');
            textList.innerHTML = textElements.map(el => `
                <div class="text-item">
                    <span class="text-id">${el.id}</span>
                    <span class="text-content">${el.text}</span>
                    <span class="text-coords">[${el.box.join(', ')}]</span>
                </div>
            `).join('') || '<div class="text-item"><span class="text-content" style="color:#999">未识别到文字</span></div>';
            
            resultSection.classList.add('show');
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
        print("正在加载 PaddleOCR 模型...")
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,
            use_gpu=is_gpu_available(),
            lang='ch',
            show_log=False,
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
    """生成 SoM 标注图"""
    try:
        image_path = get_image_from_request(request)
        if not image_path:
            return jsonify({"success": False, "error": "未提供图片"}), 400
        
        # 获取选项（兼容 multipart form 和 json）
        detect_contours = True
        return_image = True
        
        if request.is_json:
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

def detect_ui_contours(image_path, min_area=100, max_area=100000):
    """检测 UI 轮廓 - 增强版"""
    import cv2
    import numpy as np
    
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elements = []
    seen_boxes = set()
    
    def add_element(x, y, w, h):
        """添加元素，避免重复"""
        # 边界检查
        if x < 0 or y < 0 or x + w > img.shape[1] or y + h > img.shape[0]:
            return
        # 尺寸检查（最小 12x12，排除太大的）
        if w < 12 or h < 12 or w * h > max_area:
            return
        # 宽高比检查（0.1 到 10）
        aspect = w / h if h > 0 else 0
        if aspect < 0.1 or aspect > 10:
            return
        # 去重（允许 5 像素误差）
        key = (x // 5, y // 5, w // 5, h // 5)
        if key in seen_boxes:
            return
        seen_boxes.add(key)
        elements.append({
            "id": 0,
            "type": "contour",
            "box": [int(x), int(y), int(x + w), int(y + h)],
        })
    
    # 方法 1: Canny 边缘检测（多阈值）
    for low, high in [(30, 100), (50, 150), (80, 200)]:
        edges = cv2.Canny(gray, low, high)
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(cnt)
                add_element(x, y, w, h)
    
    # 方法 2: 自适应阈值
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                    cv2.THRESH_BINARY_INV, 11, 2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(cnt)
            add_element(x, y, w, h)
    
    # 方法 3: 颜色聚类检测（检测与背景不同的区域）
    # 检测图标按钮等彩色元素
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 检测高饱和度区域（彩色图标）
    saturation = hsv[:, :, 1]
    _, sat_mask = cv2.threshold(saturation, 50, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(cnt)
            add_element(x, y, w, h)
    
    # 方法 4: 检测矩形形状（按钮通常是矩形）
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/90, threshold=30, minLineLength=15, maxLineGap=5)
    
    if lines is not None:
        # 找水平和垂直线的交点形成的矩形
        h_lines = []
        v_lines = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(y2 - y1) < 5:  # 水平线
                h_lines.append((min(x1, x2), max(x1, x2), (y1 + y2) // 2))
            elif abs(x2 - x1) < 5:  # 垂直线
                v_lines.append((min(y1, y2), max(y1, y2), (x1 + x2) // 2))
    
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
