#!/usr/bin/env python3
"""
OCR-SoM + AI 自动化示例

演示如何结合 AI 模型实现视觉自动化。

Usage:
  1. 启动 OCR-SoM 服务: python server.py
  2. 设置 API Key: export OPENAI_API_KEY=xxx
  3. 运行示例: python examples/with_ai.py "点击确定按钮"
"""

import os
import sys
import json
import base64
import requests
from pathlib import Path

# 配置
OCR_SOM_URL = os.environ.get("OCR_SOM_URL", "http://localhost:5000")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def take_screenshot():
    """截取屏幕（需要安装 pillow 和 mss）"""
    try:
        import mss
        from PIL import Image
        import tempfile
        
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 主显示器
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            temp_path = tempfile.mktemp(suffix=".png")
            img.save(temp_path)
            return temp_path
    except ImportError:
        print("Please install: pip install mss pillow")
        return None


def get_som_result(image_path: str):
    """调用 OCR-SoM API 获取标注结果"""
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    resp = requests.post(f"{OCR_SOM_URL}/som", json={
        "image": image_b64,
        "detect_contours": True,
        "return_image": True,
    })
    
    return resp.json()


def ask_ai_for_target(task: str, marked_image_b64: str, elements: list):
    """让 AI 选择要操作的元素"""
    if not OPENAI_API_KEY:
        raise ValueError("Please set OPENAI_API_KEY environment variable")
    
    # 构建元素列表描述
    elements_desc = []
    for el in elements[:100]:  # 限制数量
        if el.get("text"):
            elements_desc.append(f"[{el['id']}] \"{el['text']}\"")
        else:
            elements_desc.append(f"[{el['id']}] (UI element)")
    
    prompt = f"""这是一张屏幕截图，图中的每个可交互元素都已用彩色框标注并编号。

元素列表：
{chr(10).join(elements_desc)}

任务：{task}

请分析截图，找出完成任务需要点击的元素编号。
只需返回 JSON 格式：{{"target_id": 编号, "reason": "简短说明"}}"""

    # 调用 AI
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{marked_image_b64}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 200,
    }
    
    resp = requests.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
    )
    
    result = resp.json()
    content = result["choices"][0]["message"]["content"]
    
    # 解析 JSON
    try:
        # 尝试提取 JSON
        import re
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    
    return {"error": content}


def click_element(element: dict):
    """点击元素（模拟）"""
    x1, y1, x2, y2 = element["box"]
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    print(f"  Would click at ({center_x}, {center_y})")
    
    # 实际点击（需要 pyautogui）
    # import pyautogui
    # pyautogui.click(center_x, center_y)
    
    return center_x, center_y


def main():
    if len(sys.argv) < 2:
        print("Usage: python with_ai.py <task>")
        print("Example: python with_ai.py \"点击确定按钮\"")
        return
    
    task = sys.argv[1]
    
    print("=" * 60)
    print("  OCR-SoM + AI Automation")
    print("=" * 60)
    print(f"\n  Task: {task}")
    
    # 1. 截图（这里用 demo 图片代替）
    print("\n[1] Taking screenshot...")
    demo_image = Path(__file__).parent.parent / "docs" / "demo.png"
    if demo_image.exists():
        image_path = str(demo_image)
        print(f"  Using demo image: {image_path}")
    else:
        image_path = take_screenshot()
        if not image_path:
            print("  Error: Could not take screenshot")
            return
        print(f"  Screenshot saved: {image_path}")
    
    # 2. 调用 OCR-SoM
    print("\n[2] Running OCR-SoM...")
    som_result = get_som_result(image_path)
    
    if not som_result.get("success"):
        print(f"  Error: {som_result.get('error')}")
        return
    
    print(f"  Found {som_result['count']} elements")
    
    # 3. 询问 AI
    print("\n[3] Asking AI for target...")
    if not OPENAI_API_KEY:
        print("  Skipping AI (OPENAI_API_KEY not set)")
        print("  Set it with: export OPENAI_API_KEY=your-key")
        return
    
    ai_response = ask_ai_for_target(
        task,
        som_result["marked_image"],
        som_result["elements"]
    )
    
    if "error" in ai_response:
        print(f"  AI Error: {ai_response['error']}")
        return
    
    target_id = ai_response.get("target_id")
    reason = ai_response.get("reason", "")
    print(f"  AI selected: [{target_id}] - {reason}")
    
    # 4. 获取坐标并点击
    print("\n[4] Getting coordinates...")
    element = next((e for e in som_result["elements"] if e["id"] == target_id), None)
    
    if not element:
        print(f"  Error: Element [{target_id}] not found")
        return
    
    print(f"  Element: {element.get('text', '(UI element)')}")
    print(f"  Box: {element['box']}")
    
    x, y = click_element(element)
    
    print("\n" + "=" * 60)
    print(f"  Target coordinates: ({x}, {y})")
    print("=" * 60)


if __name__ == "__main__":
    main()
