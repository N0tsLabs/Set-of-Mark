# OCR-SoM

基于 PaddleOCR 的 **Set-of-Mark** 视觉标注工具，为 AI 视觉自动化提供**像素级精确**的元素坐标。

## 什么是 SoM？

**SoM = Set-of-Mark（标记集合）** 是一种解决 AI 坐标不准问题的技术。

### 问题：AI 坐标幻觉

让 GPT-4V、Claude 等视觉模型直接输出屏幕坐标时，经常不准确：

```
用户: 请点击"确定"按钮
AI: 点击坐标 (523, 341)  ← 经常偏移 50-100 像素！
```

### 解决方案：SoM

```
1. 用 OCR 识别屏幕上所有文字，标上编号 [0] [1] [2] ...
2. 把标注图发给 AI
3. AI 只需说: "点击 42 号"
4. 从本地获取 42 号的精确坐标 → 准确点击
```

**核心思想**：AI 只负责"选择"，坐标由 OCR 保证精确。

## 效果展示

![SoM 标注效果](docs/demo.png)

## 特点

- ✅ **像素级精确** - OCR 坐标绝对精确
- ✅ **GPU 自动检测** - 有 NVIDIA 显卡自动启用 GPU 加速
- ✅ **跨平台支持** - Windows / Linux / macOS
- ✅ **HTTP API** - 提供本地 API 服务，方便调用
- ✅ **中英文支持** - PaddleOCR 对中文识别效果极佳

## 快速开始

### 一键安装

**Windows:**
```bash
python install.py
```

**Linux / macOS:**
```bash
chmod +x install.sh
./install.sh
```

安装脚本会自动：
1. 检测操作系统
2. 检测 NVIDIA GPU 和 CUDA 版本
3. 安装对应版本的 PaddlePaddle（CPU/GPU）
4. 安装其他依赖

### 安装选项

```bash
python install.py          # 自动检测
python install.py --cpu    # 强制 CPU 版本
python install.py --gpu    # 强制 GPU 版本（需要 CUDA）
```

## 使用方法

### 方式 1: 命令行

```bash
python ocr_som.py screenshot.png marked.png elements.json
```

### 方式 2: HTTP API（推荐）

启动服务：

```bash
python server.py                  # 默认端口 5000
python server.py --port 8080      # 自定义端口
python server.py --host 0.0.0.0   # 允许外部访问
```

调用 API：

```bash
# OCR 识别
curl -X POST http://localhost:5000/ocr \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/screenshot.png"}'

# 生成 SoM 标注图
curl -X POST http://localhost:5000/som \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/screenshot.png"}'
```

## HTTP API 文档

### `GET /health`

健康检查。

```json
{"status": "ok"}
```

### `GET /info`

服务信息。

```json
{
  "name": "OCR-SoM",
  "version": "1.0.0",
  "device": "GPU"
}
```

### `POST /ocr`

OCR 文字识别。

**Request:**

```json
{
  "image": "base64...",      // base64 图片
  // 或
  "image_path": "/path/to/image.png"  // 本地路径
}
```

或使用 multipart form:
```bash
curl -X POST http://localhost:5000/ocr -F "file=@screenshot.png"
```

**Response:**

```json
{
  "success": true,
  "count": 42,
  "elements": [
    {
      "id": 0,
      "type": "text",
      "text": "确定",
      "confidence": 0.99,
      "box": [100, 200, 150, 230],
      "polygon": [[100,200], [150,200], [150,230], [100,230]]
    }
  ]
}
```

### `POST /som`

生成 SoM 标注图。

**Request:**

```json
{
  "image": "base64...",
  "detect_contours": true,    // 是否检测 UI 轮廓
  "return_image": true        // 是否返回标注图
}
```

**Response:**

```json
{
  "success": true,
  "count": 50,
  "elements": [...],
  "marked_image": "base64..."  // 标注图（base64）
}
```

## 与 AI 配合使用

```python
import requests
import base64

# 1. 截图并调用 SoM API
with open('screenshot.png', 'rb') as f:
    image_b64 = base64.b64encode(f.read()).decode()

resp = requests.post('http://localhost:5000/som', json={
    'image': image_b64,
    'return_image': True
})
result = resp.json()

# 2. 保存标注图
marked_image = base64.b64decode(result['marked_image'])
with open('marked.png', 'wb') as f:
    f.write(marked_image)

# 3. 把 marked.png 发给 AI，让它选择编号
ai_response = call_your_ai("""
这是屏幕截图，每个元素都标了编号。
请告诉我应该点击哪个编号来 [完成某任务]。
只需返回: {"target_id": 编号}
""", image='marked.png')

# 4. 获取精确坐标
target_id = json.loads(ai_response)['target_id']
element = next(e for e in result['elements'] if e['id'] == target_id)
x = (element['box'][0] + element['box'][2]) // 2
y = (element['box'][1] + element['box'][3]) // 2

# 5. 执行点击
pyautogui.click(x, y)  # 像素级精确！
```

## 各语言调用示例

### Python

```python
import requests

resp = requests.post('http://localhost:5000/ocr', json={
    'image_path': '/path/to/image.png'
})
elements = resp.json()['elements']
```

### JavaScript / Node.js

```javascript
const resp = await fetch('http://localhost:5000/ocr', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ image_path: '/path/to/image.png' })
});
const { elements } = await resp.json();
```

### Go

```go
resp, _ := http.Post("http://localhost:5000/ocr", "application/json",
    strings.NewReader(`{"image_path": "/path/to/image.png"}`))
```

### Rust

```rust
let client = reqwest::Client::new();
let resp = client.post("http://localhost:5000/ocr")
    .json(&json!({"image_path": "/path/to/image.png"}))
    .send().await?;
```

## 性能

| 配置 | 首次加载 | 识别速度 |
|------|---------|---------|
| CPU (i7) | ~5s | ~10s/张 |
| GPU (RTX 3060) | ~3s | ~2s/张 |

## 系统要求

- Python 3.9 - 3.11
- 4GB+ 内存
- （可选）NVIDIA GPU + CUDA 11/12

## 常见问题

### Q: GPU 版本安装失败？

确保已安装 CUDA Toolkit：
```bash
# 检查 CUDA 版本
nvcc --version
nvidia-smi
```

### Q: 首次运行很慢？

首次运行需要下载 OCR 模型（约 20MB），之后会缓存到 `~/.paddleocr/`。

### Q: API 服务如何后台运行？

```bash
# Linux/macOS
nohup python server.py > ocr-som.log 2>&1 &

# Windows (PowerShell)
Start-Process python -ArgumentList "server.py" -WindowStyle Hidden
```

### Q: 如何配置开机自启？

Linux (systemd):
```ini
# /etc/systemd/system/ocr-som.service
[Unit]
Description=OCR-SoM API Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

MIT
