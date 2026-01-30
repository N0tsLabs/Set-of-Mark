# OCR-SoM Examples

示例代码，展示如何使用 OCR-SoM API。

## 前提条件

1. 启动 OCR-SoM 服务：
   ```bash
   python server.py
   ```

2. 服务默认运行在 `http://localhost:5000`

## 示例列表

### Python 客户端

```bash
python examples/python_client.py
```

演示：
- 健康检查
- OCR 识别
- 生成 SoM 标注图
- 根据文字查找元素

### Node.js 客户端

```bash
node examples/node_client.js
```

演示：
- 通过 fetch 调用 API
- base64 图片上传
- 元素坐标获取

### AI 自动化

```bash
export OPENAI_API_KEY=your-key
python examples/with_ai.py "点击确定按钮"
```

演示：
- 截图 + OCR-SoM
- 发送标注图给 AI
- AI 选择目标元素
- 获取精确坐标

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `API_URL` | OCR-SoM API 地址 | `http://localhost:5000` |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_BASE_URL` | OpenAI API Base URL | `https://api.openai.com/v1` |
