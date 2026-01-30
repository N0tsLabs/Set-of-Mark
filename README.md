# OCR-SoM

基于 PaddleOCR 的屏幕文字识别工具，为 AI 自动化提供**精确坐标**。

## 什么是 SoM？

**问题**：让 AI 点击屏幕上的按钮时，AI 给的坐标经常不准。

**解决**：
1. 用 OCR 识别屏幕上所有文字，给每个文字标上编号 `[0] [1] [2]...`
2. 把标注图发给 AI
3. AI 只需说"点击 42 号"
4. 程序根据编号查出精确坐标

**结果**：AI 不用猜坐标，坐标由 OCR 保证精确。

## 效果

![效果图](docs/demo.png)

每个文字都被框出来并标上了编号。

---

## 如何使用

### 第一步：安装

**Windows 用户**直接双击 `install.bat`，或者命令行运行：

```bash
python install.py
```

这会自动安装 PaddleOCR 和所有依赖。

### 第二步：启动服务

```bash
python server.py
```

看到这个输出说明成功了：

```
============================================================
  OCR-SoM API Server
============================================================
  Server: http://127.0.0.1:5000
  
Server is running at http://127.0.0.1:5000
```

### 第三步：调用

服务启动后，任何程序都可以通过 HTTP 调用它。

**测试一下**（打开另一个终端）：

```bash
curl http://localhost:5000/info
```

应该返回：
```json
{"name": "OCR-SoM", "version": "1.0.0", "device": "CPU"}
```

---

## API 接口

### 1. 识别图片中的文字

```bash
curl -X POST http://localhost:5000/ocr \
  -H "Content-Type: application/json" \
  -d '{"image_path": "C:/path/to/screenshot.png"}'
```

返回：
```json
{
  "success": true,
  "count": 42,
  "elements": [
    {"id": 0, "text": "文件", "box": [10, 20, 50, 40]},
    {"id": 1, "text": "编辑", "box": [60, 20, 100, 40]},
    ...
  ]
}
```

- `id`: 编号
- `text`: 识别的文字
- `box`: 坐标 `[左, 上, 右, 下]`

### 2. 生成标注图

```bash
curl -X POST http://localhost:5000/som \
  -H "Content-Type: application/json" \
  -d '{"image_path": "C:/path/to/screenshot.png", "return_image": true}'
```

返回 JSON 包含：
- `elements`: 所有元素列表
- `marked_image`: 标注图的 base64 编码

### 3. 健康检查

```bash
curl http://localhost:5000/health
```

---

## 完整使用流程（举例）

假设你要让 AI 自动点击屏幕上的"确定"按钮：

```
1. 截图保存为 screenshot.png

2. 调用 API：
   POST http://localhost:5000/som
   {"image_path": "screenshot.png", "return_image": true}

3. 收到返回：
   - marked_image: 标注图（每个文字都有编号）
   - elements: [{"id": 15, "text": "确定", "box": [100,200,150,230]}, ...]

4. 把标注图发给 AI，问它："要点击确定按钮，应该点哪个编号？"

5. AI 回答："点击 15 号"

6. 从 elements 里找到 15 号的 box: [100,200,150,230]

7. 计算中心点：x = (100+150)/2 = 125, y = (200+230)/2 = 215

8. 点击坐标 (125, 215) → 精确命中！
```

---

## 不用命令行？

如果你用其他语言（比如 JavaScript），直接 HTTP 请求就行：

```javascript
// 任何语言都可以这样调用
fetch('http://localhost:5000/ocr', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({image_path: 'C:/screenshot.png'})
})
.then(res => res.json())
.then(data => console.log(data.elements))
```

---

## 常见问题

### Q: 安装失败？

确保有 Python 3.9-3.11。Windows 用户可以从 https://www.python.org 下载安装。

### Q: 服务启动后怎么停止？

按 `Ctrl+C`。

### Q: 有 GPU 会更快吗？

会。安装时脚本会自动检测 NVIDIA GPU。有 GPU 大约快 5 倍。

### Q: 图片路径怎么写？

Windows 用正斜杠或双反斜杠：
- `C:/Users/xxx/screenshot.png` ✓
- `C:\\Users\\xxx\\screenshot.png` ✓
- `C:\Users\xxx\screenshot.png` ✗

---

## 文件说明

```
ocr-som/
├── install.bat      # Windows 安装（双击运行）
├── install.py       # 安装脚本
├── install.sh       # Linux/Mac 安装
├── server.py        # API 服务（主程序）
├── ocr_som.py       # 命令行工具
├── docs/demo.png    # 效果示例图
└── tests/           # 测试代码
```

## License

MIT
