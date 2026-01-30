#!/usr/bin/env python3
"""
OCR-SoM 单元测试

Usage:
  python -m pytest tests/ -v
  python tests/test_ocr.py
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestOcrSom(unittest.TestCase):
    """OCR-SoM 核心功能测试"""
    
    @classmethod
    def setUpClass(cls):
        """初始化 PaddleOCR（只执行一次）"""
        from paddleocr import PaddleOCR
        cls.ocr = PaddleOCR(
            use_angle_cls=True,
            use_gpu=False,
            lang='ch',
            show_log=False,
        )
        
        # 创建测试图片
        cls.test_image = cls._create_test_image()
    
    @classmethod
    def tearDownClass(cls):
        """清理测试图片"""
        if cls.test_image and os.path.exists(cls.test_image):
            os.unlink(cls.test_image)
    
    @classmethod
    def _create_test_image(cls):
        """创建包含文字的测试图片"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (400, 200), color='white')
            draw = ImageDraw.Draw(img)
            
            # 绘制一些文字
            draw.text((50, 30), "Hello World", fill='black')
            draw.text((50, 80), "测试文本", fill='black')
            draw.text((50, 130), "Button", fill='black')
            
            # 绘制按钮框
            draw.rectangle([40, 120, 140, 160], outline='black', width=2)
            
            # 保存
            temp_path = tempfile.mktemp(suffix='.png')
            img.save(temp_path)
            return temp_path
        except Exception as e:
            print(f"Warning: Could not create test image: {e}")
            return None
    
    def test_ocr_basic(self):
        """测试基本 OCR 功能"""
        if not self.test_image:
            self.skipTest("Test image not available")
        
        result = self.ocr.ocr(self.test_image, cls=True)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
    
    def test_ocr_returns_text(self):
        """测试 OCR 返回文字"""
        if not self.test_image:
            self.skipTest("Test image not available")
        
        result = self.ocr.ocr(self.test_image, cls=True)
        
        # 提取所有识别的文字
        texts = []
        if result and result[0]:
            for line in result[0]:
                texts.append(line[1][0])
        
        # 应该识别到一些文字
        self.assertGreater(len(texts), 0)
    
    def test_ocr_returns_boxes(self):
        """测试 OCR 返回坐标框"""
        if not self.test_image:
            self.skipTest("Test image not available")
        
        result = self.ocr.ocr(self.test_image, cls=True)
        
        if result and result[0]:
            for line in result[0]:
                box = line[0]
                # 框应该是 4 个点
                self.assertEqual(len(box), 4)
                # 每个点应该有 x, y
                for point in box:
                    self.assertEqual(len(point), 2)
                    self.assertIsInstance(point[0], (int, float))
                    self.assertIsInstance(point[1], (int, float))
    
    def test_ocr_confidence(self):
        """测试 OCR 返回置信度"""
        if not self.test_image:
            self.skipTest("Test image not available")
        
        result = self.ocr.ocr(self.test_image, cls=True)
        
        if result and result[0]:
            for line in result[0]:
                confidence = line[1][1]
                # 置信度应该在 0-1 之间
                self.assertGreaterEqual(confidence, 0)
                self.assertLessEqual(confidence, 1)


class TestServer(unittest.TestCase):
    """API 服务测试"""
    
    @classmethod
    def setUpClass(cls):
        """启动测试服务器"""
        # 导入 Flask app
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from server import app
        cls.app = app
        cls.client = app.test_client()
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
    
    def test_info_endpoint(self):
        """测试信息端点"""
        response = self.client.get('/info')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'OCR-SoM')
        self.assertIn('version', data)
        self.assertIn('device', data)
    
    def test_ocr_no_image(self):
        """测试 OCR 无图片时返回错误"""
        response = self.client.post('/ocr', 
            content_type='application/json',
            data=json.dumps({})
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])


class TestInstaller(unittest.TestCase):
    """安装脚本测试"""
    
    def test_detect_os(self):
        """测试操作系统检测"""
        from install import detect_os
        os_type = detect_os()
        self.assertIn(os_type, ['windows', 'linux', 'macos'])
    
    def test_get_python_cmd(self):
        """测试 Python 命令检测"""
        from install import get_python_cmd
        python_cmd = get_python_cmd()
        # 应该能找到 Python
        self.assertIsNotNone(python_cmd)


if __name__ == '__main__':
    unittest.main(verbosity=2)
