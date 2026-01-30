/**
 * PaddleOCR + SoM 测试脚本
 */

import { checkInstall, runOcrSom, getElementCenter, findElementByText } from './index.js';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import screenshot from 'screenshot-desktop';
import { writeFileSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main() {
  console.log('============================================================');
  console.log('  PaddleOCR + SoM 测试');
  console.log('============================================================\n');

  // 1. 检查安装
  console.log('[1/3] 检查 PaddleOCR 安装状态...');
  const { installed, python, error } = await checkInstall();
  
  if (!installed) {
    console.error(`  错误: ${error}`);
    console.log('  请先运行 install.bat 安装依赖');
    process.exit(1);
  }
  console.log(`  已安装，Python: ${python}`);

  // 2. 截图
  console.log('\n[2/3] 截取屏幕...');
  const screenshotPath = join(__dirname, 'test_screenshot.png');
  const img = await screenshot();
  writeFileSync(screenshotPath, img);
  console.log(`  已保存: ${screenshotPath}`);

  // 3. 运行 OCR + SoM
  console.log('\n[3/3] 运行 OCR + SoM...');
  const startTime = Date.now();
  
  const result = await runOcrSom(screenshotPath, {
    outputImage: join(__dirname, 'test_marked.png'),
  });
  
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`  识别到 ${result.count} 个元素（耗时 ${elapsed}s）`);
  console.log(`  标注图: ${result.outputImage}`);

  // 4. 示例：查找元素
  console.log('\n============================================================');
  console.log('  示例操作');
  console.log('============================================================\n');

  // 查找包含特定文字的元素
  const searchText = '文件';
  const matches = findElementByText(result.elements, searchText, true);
  
  if (matches.length > 0) {
    console.log(`找到 ${matches.length} 个包含"${searchText}"的元素：`);
    matches.slice(0, 5).forEach(el => {
      const center = getElementCenter(el);
      console.log(`  [${el.id}] "${el.text}" → 点击坐标: (${center.x}, ${center.y})`);
    });
  } else {
    console.log(`未找到包含"${searchText}"的元素`);
  }

  // 显示前 10 个元素
  console.log('\n前 10 个识别到的元素：');
  result.elements.slice(0, 10).forEach(el => {
    const text = el.text ? `"${el.text}"` : '(轮廓)';
    console.log(`  [${el.id}] ${text} → box: [${el.box.join(', ')}]`);
  });

  console.log('\n============================================================');
  console.log('  测试完成！');
  console.log('============================================================');
}

main().catch(console.error);
