#!/usr/bin/env python3
"""
OCR-SoM Python 客户端示例

演示如何调用 OCR-SoM API 服务。

Usage:
  1. 先启动服务: python server.py
  2. 运行示例: python examples/python_client.py
"""

import requests
import base64
import json
from pathlib import Path

API_URL = "http://localhost:5000"


def check_health():
    """检查服务是否正常"""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        return resp.json().get("status") == "ok"
    except:
        return False


def get_info():
    """获取服务信息"""
    resp = requests.get(f"{API_URL}/info")
    return resp.json()


def ocr_from_path(image_path: str):
    """通过文件路径进行 OCR"""
    resp = requests.post(f"{API_URL}/ocr", json={
        "image_path": str(image_path)
    })
    return resp.json()


def ocr_from_base64(image_path: str):
    """通过 base64 进行 OCR"""
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    resp = requests.post(f"{API_URL}/ocr", json={
        "image": image_b64
    })
    return resp.json()


def ocr_from_file(image_path: str):
    """通过文件上传进行 OCR"""
    with open(image_path, "rb") as f:
        resp = requests.post(f"{API_URL}/ocr", files={
            "file": f
        })
    return resp.json()


def som_generate(image_path: str, output_path: str = None):
    """生成 SoM 标注图"""
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    
    resp = requests.post(f"{API_URL}/som", json={
        "image": image_b64,
        "detect_contours": True,
        "return_image": True,
    })
    
    result = resp.json()
    
    if result.get("success") and result.get("marked_image"):
        if output_path:
            # 保存标注图
            image_data = base64.b64decode(result["marked_image"])
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"Saved marked image to: {output_path}")
    
    return result


def find_element_by_text(elements: list, text: str, fuzzy: bool = False):
    """根据文字查找元素"""
    if fuzzy:
        return [e for e in elements if text in e.get("text", "")]
    return [e for e in elements if e.get("text") == text]


def get_element_center(element: dict):
    """获取元素中心点"""
    x1, y1, x2, y2 = element["box"]
    return (x1 + x2) // 2, (y1 + y2) // 2


def main():
    print("=" * 60)
    print("  OCR-SoM Python Client Example")
    print("=" * 60)
    
    # 1. 检查服务
    print("\n[1] Checking service...")
    if not check_health():
        print("  Error: Service not available!")
        print("  Please start the server: python server.py")
        return
    print("  Service is running!")
    
    # 2. 获取信息
    print("\n[2] Getting service info...")
    info = get_info()
    print(f"  Name: {info['name']}")
    print(f"  Version: {info['version']}")
    print(f"  Device: {info['device']}")
    
    # 3. 查找测试图片
    demo_image = Path(__file__).parent.parent / "docs" / "demo.png"
    if not demo_image.exists():
        print("\n  No demo image found, skipping OCR test")
        return
    
    # 4. OCR 测试
    print(f"\n[3] Running OCR on: {demo_image}")
    result = ocr_from_path(str(demo_image))
    
    if result.get("success"):
        print(f"  Found {result['count']} text elements")
        
        # 显示前 5 个
        print("\n  First 5 elements:")
        for el in result["elements"][:5]:
            text = el.get("text", "")[:30]
            conf = el.get("confidence", 0)
            box = el.get("box", [])
            print(f"    [{el['id']}] \"{text}\" (conf: {conf:.2f}) @ {box}")
    else:
        print(f"  Error: {result.get('error')}")
    
    # 5. SoM 测试
    print(f"\n[4] Generating SoM marked image...")
    output_path = Path(__file__).parent / "output_marked.png"
    som_result = som_generate(str(demo_image), str(output_path))
    
    if som_result.get("success"):
        print(f"  Total elements: {som_result['count']}")
        
        # 示例：查找包含特定文字的元素
        elements = som_result["elements"]
        matches = find_element_by_text(elements, "Google", fuzzy=True)
        if matches:
            el = matches[0]
            x, y = get_element_center(el)
            print(f"\n  Found 'Google' at element [{el['id']}], center: ({x}, {y})")
    
    print("\n" + "=" * 60)
    print("  Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
