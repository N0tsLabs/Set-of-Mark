#!/usr/bin/env python3
"""
OCR + SoM (Set-of-Mark) 视觉标注方案

功能：
1. 使用 PaddleOCR 识别截图中所有文字及精确坐标
2. 给每个元素画框并编号 (SoM)
3. 输出标注后的图片和元素列表 JSON

用法：
  python ocr_som.py <input_image> [output_image] [output_json]

示例：
  python ocr_som.py screenshot.png marked.png elements.json
"""

import sys
import json
import os
from pathlib import Path

# 设置环境变量，禁用 GPU 和 oneDNN
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load_paddleocr():
    """延迟加载 PaddleOCR（首次加载较慢）"""
    from paddleocr import PaddleOCR
    # PaddleOCR 2.7.x API
    ocr = PaddleOCR(
        use_angle_cls=True,
        use_gpu=False,
        lang='ch',
        show_log=False,
    )
    return ocr


def run_ocr(ocr, image_path):
    """
    运行 OCR 识别
    返回: [(text, confidence, [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]), ...]
    """
    result = ocr.ocr(str(image_path), cls=True)
    
    elements = []
    if result and result[0]:
        for line in result[0]:
            box = line[0]  # 四个角点坐标
            text = line[1][0]  # 文字内容
            confidence = line[1][1]  # 置信度
            
            # 计算边界框
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            x1, y1 = min(x_coords), min(y_coords)
            x2, y2 = max(x_coords), max(y_coords)
            
            elements.append({
                'text': text,
                'confidence': float(confidence),
                'box': [int(x1), int(y1), int(x2), int(y2)],
                'polygon': [[int(p[0]), int(p[1])] for p in box],
            })
    
    return elements


def detect_ui_contours(image_path, min_area=500, max_area=100000):
    """
    使用 OpenCV 检测 UI 元素轮廓（按钮、图标等）
    """
    img = cv2.imread(str(image_path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 边缘检测
    edges = cv2.Canny(gray, 50, 150)
    
    # 膨胀操作连接断开的边缘
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    
    # 查找轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    ui_elements = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area < area < max_area:
            x, y, w, h = cv2.boundingRect(contour)
            # 过滤掉太扁或太窄的
            aspect_ratio = w / h if h > 0 else 0
            if 0.1 < aspect_ratio < 10:
                ui_elements.append({
                    'type': 'ui_element',
                    'box': [x, y, x + w, y + h],
                    'area': area,
                })
    
    return ui_elements


def merge_elements(ocr_elements, ui_elements):
    """
    合并 OCR 文字和 UI 轮廓，去重
    """
    all_elements = []
    
    # 先添加 OCR 元素（优先级更高）
    for i, el in enumerate(ocr_elements):
        all_elements.append({
            'id': len(all_elements),
            'type': 'text',
            'text': el['text'],
            'confidence': el['confidence'],
            'box': el['box'],
        })
    
    # 添加不与 OCR 元素重叠的 UI 元素
    for ui_el in ui_elements:
        ui_box = ui_el['box']
        is_overlapping = False
        
        for ocr_el in ocr_elements:
            ocr_box = ocr_el['box']
            # 检查重叠
            if (ui_box[0] < ocr_box[2] and ui_box[2] > ocr_box[0] and
                ui_box[1] < ocr_box[3] and ui_box[3] > ocr_box[1]):
                # 计算重叠面积
                overlap_x = min(ui_box[2], ocr_box[2]) - max(ui_box[0], ocr_box[0])
                overlap_y = min(ui_box[3], ocr_box[3]) - max(ui_box[1], ocr_box[1])
                overlap_area = overlap_x * overlap_y
                ui_area = (ui_box[2] - ui_box[0]) * (ui_box[3] - ui_box[1])
                if overlap_area > ui_area * 0.3:  # 30% 以上重叠则认为是同一元素
                    is_overlapping = True
                    break
        
        if not is_overlapping:
            all_elements.append({
                'id': len(all_elements),
                'type': 'icon',
                'text': '',
                'box': ui_box,
            })
    
    return all_elements


def draw_som_marks(image_path, elements, output_path):
    """
    在图片上绘制 SoM 标记（带编号的彩色框）
    """
    # 使用 PIL 绘制（支持中文）
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # 尝试加载字体
    try:
        # Windows 中文字体
        font = ImageFont.truetype("msyh.ttc", 16)
        font_small = ImageFont.truetype("msyh.ttc", 12)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
            font_small = font
    
    # 颜色列表（循环使用）
    colors = [
        (255, 0, 0),      # 红
        (0, 255, 0),      # 绿
        (0, 0, 255),      # 蓝
        (255, 165, 0),    # 橙
        (128, 0, 255),    # 紫
        (0, 255, 255),    # 青
        (255, 0, 255),    # 品红
        (255, 255, 0),    # 黄
    ]
    
    for el in elements:
        idx = el['id']
        box = el['box']
        color = colors[idx % len(colors)]
        
        x1, y1, x2, y2 = box
        
        # 绘制矩形框
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        
        # 绘制编号标签背景
        label = str(idx)
        label_bbox = font.getbbox(label)
        label_w = label_bbox[2] - label_bbox[0] + 6
        label_h = label_bbox[3] - label_bbox[1] + 4
        
        # 标签位置（左上角）
        label_x = max(0, x1)
        label_y = max(0, y1 - label_h - 2)
        if label_y < 0:
            label_y = y1 + 2
        
        # 绘制标签背景
        draw.rectangle(
            [label_x, label_y, label_x + label_w, label_y + label_h],
            fill=color
        )
        
        # 绘制编号文字
        draw.text((label_x + 3, label_y + 2), label, fill=(255, 255, 255), font=font)
    
    # 保存图片
    img.save(output_path)
    print(f"已保存标注图片: {output_path}")
    
    return str(output_path)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    input_image = sys.argv[1]
    output_image = sys.argv[2] if len(sys.argv) > 2 else input_image.replace('.', '_marked.')
    output_json = sys.argv[3] if len(sys.argv) > 3 else input_image.replace('.png', '.json').replace('.jpg', '.json')
    
    if not os.path.exists(input_image):
        print(f"Error: Input image not found: {input_image}")
        sys.exit(1)
    
    print("=" * 60)
    print("OCR + SoM Visual Marking")
    print("=" * 60)
    
    # 1. Load PaddleOCR
    print("\n[1/4] Loading PaddleOCR...")
    ocr = load_paddleocr()
    
    # 2. Run OCR
    print("\n[2/4] Running OCR...")
    ocr_elements = run_ocr(ocr, input_image)
    print(f"  Found {len(ocr_elements)} text elements")
    
    # 3. Detect UI contours
    print("\n[3/4] Detecting UI contours...")
    ui_elements = detect_ui_contours(input_image)
    print(f"  Found {len(ui_elements)} UI elements")
    
    # 4. Merge elements
    all_elements = merge_elements(ocr_elements, ui_elements)
    print(f"  Total {len(all_elements)} elements after merge")
    
    # 5. Draw SoM marks
    print("\n[4/4] Drawing SoM marks...")
    draw_som_marks(input_image, all_elements, output_image)
    
    # 6. Save JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'image': input_image,
            'elements': all_elements,
            'count': len(all_elements),
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved elements: {output_json}")
    
    print("\n" + "=" * 60)
    print(f"Done! {len(all_elements)} elements marked")
    print("=" * 60)


if __name__ == '__main__':
    main()
