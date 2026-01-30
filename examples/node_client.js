/**
 * OCR-SoM Node.js 客户端示例
 * 
 * 演示如何调用 OCR-SoM API 服务。
 * 
 * Usage:
 *   1. 先启动服务: python server.py
 *   2. 运行示例: node examples/node_client.js
 */

const fs = require('fs');
const path = require('path');

const API_URL = process.env.API_URL || 'http://localhost:5000';

async function checkHealth() {
  try {
    const resp = await fetch(`${API_URL}/health`);
    const data = await resp.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}

async function getInfo() {
  const resp = await fetch(`${API_URL}/info`);
  return resp.json();
}

async function ocrFromPath(imagePath) {
  const resp = await fetch(`${API_URL}/ocr`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_path: imagePath }),
  });
  return resp.json();
}

async function ocrFromBase64(imagePath) {
  const imageBuffer = fs.readFileSync(imagePath);
  const imageB64 = imageBuffer.toString('base64');
  
  const resp = await fetch(`${API_URL}/ocr`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imageB64 }),
  });
  return resp.json();
}

async function somGenerate(imagePath, outputPath = null) {
  const imageBuffer = fs.readFileSync(imagePath);
  const imageB64 = imageBuffer.toString('base64');
  
  const resp = await fetch(`${API_URL}/som`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image: imageB64,
      detect_contours: true,
      return_image: true,
    }),
  });
  
  const result = await resp.json();
  
  if (result.success && result.marked_image && outputPath) {
    const imageData = Buffer.from(result.marked_image, 'base64');
    fs.writeFileSync(outputPath, imageData);
    console.log(`Saved marked image to: ${outputPath}`);
  }
  
  return result;
}

function findElementByText(elements, text, fuzzy = false) {
  if (fuzzy) {
    return elements.filter(e => e.text && e.text.includes(text));
  }
  return elements.filter(e => e.text === text);
}

function getElementCenter(element) {
  const [x1, y1, x2, y2] = element.box;
  return {
    x: Math.round((x1 + x2) / 2),
    y: Math.round((y1 + y2) / 2),
  };
}

async function main() {
  console.log('='.repeat(60));
  console.log('  OCR-SoM Node.js Client Example');
  console.log('='.repeat(60));
  
  // 1. 检查服务
  console.log('\n[1] Checking service...');
  if (!await checkHealth()) {
    console.log('  Error: Service not available!');
    console.log('  Please start the server: python server.py');
    return;
  }
  console.log('  Service is running!');
  
  // 2. 获取信息
  console.log('\n[2] Getting service info...');
  const info = await getInfo();
  console.log(`  Name: ${info.name}`);
  console.log(`  Version: ${info.version}`);
  console.log(`  Device: ${info.device}`);
  
  // 3. 查找测试图片
  const demoImage = path.join(__dirname, '..', 'docs', 'demo.png');
  if (!fs.existsSync(demoImage)) {
    console.log('\n  No demo image found, skipping OCR test');
    return;
  }
  
  // 4. OCR 测试
  console.log(`\n[3] Running OCR on: ${demoImage}`);
  const result = await ocrFromPath(demoImage);
  
  if (result.success) {
    console.log(`  Found ${result.count} text elements`);
    
    console.log('\n  First 5 elements:');
    result.elements.slice(0, 5).forEach(el => {
      const text = (el.text || '').slice(0, 30);
      const conf = (el.confidence || 0).toFixed(2);
      console.log(`    [${el.id}] "${text}" (conf: ${conf}) @ [${el.box.join(', ')}]`);
    });
  } else {
    console.log(`  Error: ${result.error}`);
  }
  
  // 5. SoM 测试
  console.log('\n[4] Generating SoM marked image...');
  const outputPath = path.join(__dirname, 'output_marked.png');
  const somResult = await somGenerate(demoImage, outputPath);
  
  if (somResult.success) {
    console.log(`  Total elements: ${somResult.count}`);
    
    // 示例：查找包含特定文字的元素
    const matches = findElementByText(somResult.elements, 'Google', true);
    if (matches.length > 0) {
      const el = matches[0];
      const { x, y } = getElementCenter(el);
      console.log(`\n  Found 'Google' at element [${el.id}], center: (${x}, ${y})`);
    }
  }
  
  console.log('\n' + '='.repeat(60));
  console.log('  Done!');
  console.log('='.repeat(60));
}

main().catch(console.error);
