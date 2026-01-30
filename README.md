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
4. 从本地 JSON 获取 42 号的精确坐标 → 准确点击
```

**核心思想**：
- ❌ AI 不擅长：估计像素坐标
- ✅ AI 擅长：理解语义、选择目标
- ✅ OCR 擅长：提供精确坐标

把任务拆分给各自擅长的模块！

## 效果展示

![SoM 标注效果](docs/demo.png)

## 特点

- ✅ **像素级精确** - OCR 识别的文字坐标绝对精确
- ✅ **中英文支持** - PaddleOCR 对中文识别效果极佳
- ✅ **CPU 运行** - 无需 GPU，普通电脑即可运行
- ✅ **一键安装** - Windows 用户双击 `install.bat` 即可
- ✅ **Node.js 封装** - 可直接在 Node.js 项目中调用

## 快速开始

### Windows 一键安装

```bash
# 双击运行
install.bat
```

### 手动安装

```bash
# 1. 确保已安装 Python 3.9+
python --version

# 2. 安装依赖
pip install paddlepaddle==2.6.2 paddleocr==2.7.3 "numpy<2" opencv-python-headless Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 使用方法

### 命令行

```bash
python ocr_som.py <输入图片> [输出标注图] [输出JSON]

# 示例
python ocr_som.py screenshot.png marked.png elements.json
```

### Node.js

```javascript
import { runOcrSom, checkInstall, installDeps } from 'ocr-som';

// 检查安装
const { installed } = await checkInstall();
if (!installed) {
  await installDeps();
}

// 运行 OCR + SoM
const result = await runOcrSom('screenshot.png');

console.log(`识别到 ${result.count} 个元素`);

// 获取某个元素的坐标
const element = result.elements.find(e => e.text === '确定');
if (element) {
  const [x1, y1, x2, y2] = element.box;
  const centerX = (x1 + x2) / 2;
  const centerY = (y1 + y2) / 2;
  console.log(`点击坐标: (${centerX}, ${centerY})`);
}
```

### 与 AI 配合使用

```javascript
import { runOcrSom, getElementById, getElementCenter } from 'ocr-som';

// 1. 截图并运行 OCR-SoM
const result = await runOcrSom('screenshot.png', {
  outputImage: 'marked.png'
});

// 2. 把 marked.png 发给 AI，让它选择要点击的编号
const aiResponse = await askAI(`
  这是屏幕截图，每个元素都标了编号。
  请告诉我应该点击哪个编号来 [完成某任务]。
  只需返回: {"target_id": 编号}
`, 'marked.png');

// 3. 获取精确坐标
const targetId = JSON.parse(aiResponse).target_id;
const element = getElementById(result.elements, targetId);
const { x, y } = getElementCenter(element);

// 4. 执行点击
await click(x, y);  // 像素级精确！
```

## 输出格式

### 标注图

每个识别到的元素都会被框出并标注编号。

### JSON 数据

```json
{
  "image": "screenshot.png",
  "count": 130,
  "elements": [
    {
      "id": 0,
      "type": "text",
      "text": "确定",
      "confidence": 0.99,
      "box": [100, 200, 150, 230]
    },
    {
      "id": 1,
      "type": "contour",
      "box": [300, 400, 380, 450]
    }
  ]
}
```

**字段说明**：
- `id`: 元素编号（与图上标注对应）
- `type`: 类型，`text`（文字）或 `contour`（轮廓）
- `text`: 识别的文字内容（仅 text 类型）
- `confidence`: 置信度 0-1（仅 text 类型）
- `box`: 边界框 `[x1, y1, x2, y2]`（左上角和右下角坐标）

## API 参考

### `checkInstall()`

检查 PaddleOCR 是否已安装。

```javascript
const { installed, python, error } = await checkInstall();
```

### `installDeps(options?)`

安装 PaddleOCR 依赖。

```javascript
await installDeps({
  onProgress: (msg) => console.log(msg)
});
```

### `runOcrSom(inputImage, options?)`

运行 OCR + SoM 标注。

| 参数 | 类型 | 说明 |
|------|------|------|
| inputImage | string | 输入图片路径 |
| options.outputImage | string | 输出标注图路径（可选） |
| options.detectContours | boolean | 是否检测 UI 轮廓（默认 true） |

返回值：
```javascript
{
  elements: [...],     // 元素列表
  outputImage: '...',  // 标注图路径
  count: 130           // 元素数量
}
```

### `getElementById(elements, id)`

根据编号获取元素。

### `getElementCenter(element)`

获取元素中心点坐标。

```javascript
const { x, y } = getElementCenter(element);
```

### `findElementByText(elements, text, fuzzy?)`

根据文字查找元素。

```javascript
// 精确匹配
const btns = findElementByText(elements, '确定');

// 模糊匹配
const items = findElementByText(elements, '设置', true);
```

## 性能

| 指标 | 数值 |
|------|------|
| 首次加载 | ~5s（加载模型） |
| 后续识别 | ~10s（1920x1080 图片） |
| 内存占用 | ~500MB |

## 系统要求

- Windows 10/11（macOS/Linux 需手动安装）
- Python 3.9 - 3.11
- 4GB+ 内存

## 常见问题

### Q: 首次运行很慢？

A: 首次运行需要下载 OCR 模型（约 20MB），之后会缓存到 `~/.paddleocr/`。

### Q: 如何识别图标/按钮？

A: 纯图标无法通过 OCR 识别。可以：
1. 启用轮廓检测（默认开启）
2. 配合 Windows UI Automation 获取更多元素

### Q: 支持 macOS/Linux 吗？

A: 支持，但需要手动安装 Python 和依赖，`install.bat` 仅适用于 Windows。

## 相关项目

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - 百度开源 OCR 工具
- [Set-of-Mark](https://github.com/microsoft/SoM) - 微软 SoM 论文实现

## License

MIT
