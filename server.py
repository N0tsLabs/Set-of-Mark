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
    <title>OCR-SoM</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { 
            height: 100%; 
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #fff;
        }
        input[type="file"] { display: none; }
        .hidden { display: none !important; }
        
        /* ===== 首页 ===== */
        .home {
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .home-title {
            font-size: 48px;
            font-weight: 300;
            color: #222;
            margin-bottom: 8px;
            letter-spacing: -1px;
        }
        .home-subtitle {
            font-size: 15px;
            color: #999;
            margin-bottom: 48px;
        }
        .home-btn {
            background: #222;
            color: #fff;
            border: none;
            padding: 16px 48px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .home-btn:hover { background: #444; transform: scale(1.02); }
        .home-hint {
            margin-top: 16px;
            font-size: 13px;
            color: #bbb;
        }
        .home-device {
            position: absolute;
            bottom: 24px;
            font-size: 12px;
            color: #ccc;
        }
        
        /* ===== 加载页 ===== */
        .loading-page {
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .spinner {
            width: 40px; height: 40px;
            border: 3px solid #eee;
            border-top-color: #222;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { color: #666; font-size: 15px; }
        
        /* ===== 结果页 ===== */
        .result-page {
            height: 100%;
            display: flex;
        }
        
        /* 左侧面板 */
        .left-panel {
            width: 360px;
            min-width: 360px;
            height: 100%;
            border-right: 1px solid #eee;
            display: flex;
            flex-direction: column;
            background: #fafafa;
        }
        .panel-header {
            padding: 16px 20px;
            border-bottom: 1px solid #eee;
            background: #fff;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .panel-title { font-size: 15px; font-weight: 600; color: #333; }
        .panel-stats { font-size: 12px; color: #999; }
        .panel-actions { display: flex; gap: 8px; }
        .panel-btn {
            background: #f5f5f5;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            color: #666;
            cursor: pointer;
        }
        .panel-btn:hover { background: #eee; }
        
        .element-list {
            flex: 1;
            overflow-y: auto;
        }
        .element-item {
            padding: 12px 20px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background 0.15s;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .element-item:hover { background: #f0f0f0; }
        .element-item.active { background: #e8f4ff; }
        .element-id {
            background: #222;
            color: #fff;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            min-width: 28px;
            text-align: center;
        }
        .element-item.active .element-id { background: #0066cc; }
        .element-info { flex: 1; min-width: 0; }
        .element-text {
            font-size: 14px;
            color: #333;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .element-meta {
            font-size: 11px;
            color: #999;
            margin-top: 2px;
            font-family: monospace;
        }
        
        /* 右侧图片查看器 */
        .right-panel {
            flex: 1;
            height: 100%;
            background: #f5f5f5;
            position: relative;
            overflow: hidden;
        }
        .viewer-toolbar {
            position: absolute;
            top: 16px;
            right: 16px;
            display: flex;
            gap: 8px;
            z-index: 10;
        }
        .viewer-btn {
            background: rgba(255,255,255,0.95);
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.2s;
        }
        .viewer-btn:hover { background: #fff; transform: scale(1.05); }
        
        .viewer-container {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: grab;
        }
        .viewer-container:active { cursor: grabbing; }
        .viewer-canvas {
            position: relative;
            transform-origin: center center;
            transition: transform 0.1s ease-out;
        }
        .viewer-img {
            display: block;
            max-width: none;
            box-shadow: 0 4px 24px rgba(0,0,0,0.15);
            border-radius: 4px;
        }
        
        /* 高亮框 */
        .highlight-box {
            position: absolute;
            border: 3px solid #0066cc;
            background: rgba(0, 102, 204, 0.15);
            border-radius: 4px;
            pointer-events: none;
            transition: all 0.2s;
            box-shadow: 0 0 0 4px rgba(0, 102, 204, 0.3);
        }
        
        /* 缩放提示 */
        .zoom-indicator {
            position: absolute;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            color: #fff;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
        }
        
        /* 错误提示 */
        .error-msg {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #e53935;
            font-size: 15px;
        }
    </style>
</head>
<body>
    <!-- 首页 -->
    <div class="home" id="homePage">
        <h1 class="home-title">OCR-SoM</h1>
        <p class="home-subtitle">基于 PaddleOCR 的视觉标注工具</p>
        <button class="home-btn" id="uploadBtn">选择图片</button>
        <p class="home-hint">支持拖拽上传 PNG、JPG、GIF</p>
        <div class="home-device" id="deviceInfo"></div>
    </div>
    <input type="file" id="fileInput" accept="image/*">
    
    <!-- 加载页 -->
    <div class="loading-page hidden" id="loadingPage">
        <div class="spinner"></div>
        <div class="loading-text">正在识别...</div>
    </div>
    
    <!-- 结果页 -->
    <div class="result-page hidden" id="resultPage">
        <div class="left-panel">
            <div class="panel-header">
                <div>
                    <div class="panel-title">识别结果</div>
                    <div class="panel-stats" id="stats"></div>
                </div>
                <div class="panel-actions">
                    <button class="panel-btn" id="newUploadBtn">重新上传</button>
                </div>
            </div>
            <div class="element-list" id="elementList"></div>
        </div>
        <div class="right-panel">
            <div class="viewer-toolbar">
                <button class="viewer-btn" id="zoomInBtn" title="放大">+</button>
                <button class="viewer-btn" id="zoomOutBtn" title="缩小">−</button>
                <button class="viewer-btn" id="resetBtn" title="重置">↺</button>
            </div>
            <div class="viewer-container" id="viewerContainer">
                <div class="viewer-canvas" id="viewerCanvas">
                    <img class="viewer-img" id="resultImg">
                    <div class="highlight-box hidden" id="highlightBox"></div>
                </div>
            </div>
            <div class="zoom-indicator" id="zoomIndicator">100%</div>
        </div>
    </div>
    
    <script>
        // 元素引用
        const homePage = document.getElementById('homePage');
        const loadingPage = document.getElementById('loadingPage');
        const resultPage = document.getElementById('resultPage');
        const uploadBtn = document.getElementById('uploadBtn');
        const newUploadBtn = document.getElementById('newUploadBtn');
        const fileInput = document.getElementById('fileInput');
        const deviceInfo = document.getElementById('deviceInfo');
        const stats = document.getElementById('stats');
        const elementList = document.getElementById('elementList');
        const resultImg = document.getElementById('resultImg');
        const viewerContainer = document.getElementById('viewerContainer');
        const viewerCanvas = document.getElementById('viewerCanvas');
        const highlightBox = document.getElementById('highlightBox');
        const zoomIndicator = document.getElementById('zoomIndicator');
        const zoomInBtn = document.getElementById('zoomInBtn');
        const zoomOutBtn = document.getElementById('zoomOutBtn');
        const resetBtn = document.getElementById('resetBtn');
        
        // 状态
        let currentElements = [];
        let scale = 1;
        let translateX = 0;
        let translateY = 0;
        let isDragging = false;
        let startX, startY;
        let imgNaturalWidth = 0;
        let imgNaturalHeight = 0;
        
        // 获取设备信息
        fetch('/info').then(r => r.json()).then(data => {
            deviceInfo.textContent = `运行于 ${data.device}`;
        });
        
        // 上传按钮
        uploadBtn.addEventListener('click', () => fileInput.click());
        newUploadBtn.addEventListener('click', () => fileInput.click());
        
        // 拖拽上传
        document.body.addEventListener('dragover', e => {
            e.preventDefault();
            if (!resultPage.classList.contains('hidden')) return;
            homePage.style.background = '#f8f8f8';
        });
        document.body.addEventListener('dragleave', () => {
            homePage.style.background = '';
        });
        document.body.addEventListener('drop', e => {
            e.preventDefault();
            homePage.style.background = '';
            if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
        });
        
        // 文件选择
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) handleFile(fileInput.files[0]);
        });
        
        // 处理文件
        async function handleFile(file) {
            if (!file.type.startsWith('image/')) return;
            
            showPage('loading');
            
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
                    alert(data.error || '识别失败');
                    showPage('home');
                }
            } catch (err) {
                alert('请求失败: ' + err.message);
                showPage('home');
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
        
        function showPage(page) {
            homePage.classList.toggle('hidden', page !== 'home');
            loadingPage.classList.toggle('hidden', page !== 'loading');
            resultPage.classList.toggle('hidden', page !== 'result');
        }
        
        function showResult(data) {
            currentElements = data.elements;
            
            // 显示图片
            resultImg.src = 'data:image/png;base64,' + data.marked_image;
            resultImg.onload = () => {
                imgNaturalWidth = resultImg.naturalWidth;
                imgNaturalHeight = resultImg.naturalHeight;
                resetView();
            };
            
            // 统计
            const textCount = data.elements.filter(e => e.type === 'text').length;
            stats.textContent = `${data.count} 个元素，${textCount} 个文字`;
            
            // 元素列表
            elementList.innerHTML = data.elements.map((el, idx) => `
                <div class="element-item" data-idx="${idx}" data-box="${el.box.join(',')}">
                    <span class="element-id">${el.id}</span>
                    <div class="element-info">
                        <div class="element-text">${el.text || '[UI 元素]'}</div>
                        <div class="element-meta">[${el.box.join(', ')}]</div>
                    </div>
                </div>
            `).join('');
            
            // 点击元素高亮
            elementList.querySelectorAll('.element-item').forEach(item => {
                item.addEventListener('click', () => {
                    // 更新选中状态
                    elementList.querySelectorAll('.element-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    
                    // 显示高亮框
                    const box = item.dataset.box.split(',').map(Number);
                    showHighlight(box);
                });
            });
            
            showPage('result');
        }
        
        function showHighlight(box) {
            const [x1, y1, x2, y2] = box;
            const scaleRatio = resultImg.width / imgNaturalWidth;
            
            highlightBox.style.left = (x1 * scaleRatio) + 'px';
            highlightBox.style.top = (y1 * scaleRatio) + 'px';
            highlightBox.style.width = ((x2 - x1) * scaleRatio) + 'px';
            highlightBox.style.height = ((y2 - y1) * scaleRatio) + 'px';
            highlightBox.classList.remove('hidden');
        }
        
        // 缩放控制
        function updateTransform() {
            viewerCanvas.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
            zoomIndicator.textContent = Math.round(scale * 100) + '%';
        }
        
        function resetView() {
            scale = 1;
            translateX = 0;
            translateY = 0;
            updateTransform();
            highlightBox.classList.add('hidden');
            elementList.querySelectorAll('.element-item').forEach(i => i.classList.remove('active'));
        }
        
        zoomInBtn.addEventListener('click', () => {
            scale = Math.min(scale * 1.25, 5);
            updateTransform();
        });
        
        zoomOutBtn.addEventListener('click', () => {
            scale = Math.max(scale / 1.25, 0.25);
            updateTransform();
        });
        
        resetBtn.addEventListener('click', resetView);
        
        // 滚轮缩放
        viewerContainer.addEventListener('wheel', e => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            scale = Math.max(0.25, Math.min(5, scale * delta));
            updateTransform();
        });
        
        // 拖动
        viewerContainer.addEventListener('mousedown', e => {
            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
        });
        
        document.addEventListener('mousemove', e => {
            if (!isDragging) return;
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            updateTransform();
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
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

def detect_ui_contours(image_path, min_area=200, max_area=80000):
    """检测 UI 轮廓 - 平衡版"""
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
            # 计算交集
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
        # 边界检查
        if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
            return
        # 尺寸检查（最小 16x16）
        if w < 16 or h < 16 or w * h < min_area or w * h > max_area:
            return
        # 宽高比检查（0.15 到 7）
        aspect = w / h if h > 0 else 0
        if aspect < 0.15 or aspect > 7:
            return
        # 去重
        if is_duplicate(x, y, w, h):
            return
        seen_boxes.append((x, y, w, h))
        elements.append({
            "id": 0,
            "type": "contour",
            "box": [int(x), int(y), int(x + w), int(y + h)],
        })
    
    # 方法 1: Canny 边缘检测（两组参数）
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
                fill_ratio = area / rect_area if rect_area > 0 else 0
                if fill_ratio > 0.3:
                    add_element(x, y, w, h)
    
    # 方法 2: 检测高饱和度区域（彩色图标）
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    _, sat_mask = cv2.threshold(saturation, 40, 255, cv2.THRESH_BINARY)
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
