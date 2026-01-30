/**
 * PaddleOCR + SoM Node.js 封装
 * 
 * 使用方法:
 *   const { runOcrSom, installDeps, checkInstall } = require('./ocr-som');
 *   
 *   // 检查是否已安装
 *   const installed = await checkInstall();
 *   
 *   // 安装依赖（首次使用）
 *   await installDeps();
 *   
 *   // 运行 OCR + SoM
 *   const result = await runOcrSom('screenshot.png');
 *   console.log(result.elements); // 元素列表
 */

import { spawn, execSync } from 'child_process';
import { existsSync, readFileSync, unlinkSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { tmpdir } from 'os';

const __dirname = dirname(fileURLToPath(import.meta.url));

// 查找 Python 路径
function findPython() {
  const candidates = [
    'python',
    'python3',
    'py',
    // Windows 默认安装路径
    join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
    join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
    join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python39', 'python.exe'),
  ];

  for (const cmd of candidates) {
    try {
      execSync(`"${cmd}" --version`, { stdio: 'pipe' });
      return cmd;
    } catch {
      // 继续尝试
    }
  }
  return null;
}

/**
 * 检查 PaddleOCR 是否已安装
 */
export async function checkInstall() {
  const python = findPython();
  if (!python) {
    return { installed: false, error: 'Python not found' };
  }

  try {
    execSync(`"${python}" -c "from paddleocr import PaddleOCR"`, { stdio: 'pipe' });
    return { installed: true, python };
  } catch {
    return { installed: false, python, error: 'PaddleOCR not installed' };
  }
}

/**
 * 安装依赖
 */
export async function installDeps(options = {}) {
  const { onProgress } = options;
  const python = findPython();

  if (!python) {
    throw new Error('Python not found. Please install Python 3.9+ first.');
  }

  return new Promise((resolve, reject) => {
    const args = [
      '-m', 'pip', 'install',
      'paddlepaddle==2.6.2',
      'paddleocr==2.7.3',
      'numpy<2',
      'opencv-python-headless',
      'Pillow',
      '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple',
    ];

    const proc = spawn(python, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let output = '';
    proc.stdout.on('data', (data) => {
      output += data.toString();
      onProgress?.(`Installing: ${data.toString().trim()}`);
    });

    proc.stderr.on('data', (data) => {
      output += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ success: true });
      } else {
        reject(new Error(`Install failed: ${output}`));
      }
    });
  });
}

/**
 * 运行 OCR + SoM
 * @param {string} inputImage - 输入图片路径
 * @param {object} options - 选项
 * @param {string} options.outputImage - 输出标注图路径（可选）
 * @param {boolean} options.detectContours - 是否检测 UI 轮廓（默认 true）
 * @returns {Promise<{elements: Array, outputImage: string}>}
 */
export async function runOcrSom(inputImage, options = {}) {
  const {
    outputImage = join(tmpdir(), `ocr-som-${Date.now()}.png`),
    detectContours = true,
  } = options;

  const check = await checkInstall();
  if (!check.installed) {
    throw new Error(check.error + '. Run installDeps() first.');
  }

  const python = check.python;
  const scriptPath = join(__dirname, 'ocr_som.py');
  const jsonPath = join(tmpdir(), `ocr-som-${Date.now()}.json`);

  return new Promise((resolve, reject) => {
    const args = [scriptPath, inputImage, outputImage, jsonPath];
    if (!detectContours) {
      args.push('--no-contours');
    }

    const proc = spawn(python, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stderr = '';
    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0 && existsSync(jsonPath)) {
        try {
          const result = JSON.parse(readFileSync(jsonPath, 'utf-8'));
          // 清理临时文件
          try { unlinkSync(jsonPath); } catch {}
          
          resolve({
            elements: result.elements,
            outputImage,
            count: result.elements.length,
          });
        } catch (e) {
          reject(new Error(`Failed to parse result: ${e.message}`));
        }
      } else {
        reject(new Error(`OCR failed: ${stderr}`));
      }
    });
  });
}

/**
 * 根据编号获取元素
 */
export function getElementById(elements, id) {
  return elements.find(e => e.id === id);
}

/**
 * 获取元素中心点
 */
export function getElementCenter(element) {
  const [x1, y1, x2, y2] = element.box;
  return {
    x: Math.round((x1 + x2) / 2),
    y: Math.round((y1 + y2) / 2),
  };
}

/**
 * 根据文字查找元素
 */
export function findElementByText(elements, text, fuzzy = false) {
  if (fuzzy) {
    return elements.filter(e => e.text && e.text.includes(text));
  }
  return elements.filter(e => e.text === text);
}

export default {
  checkInstall,
  installDeps,
  runOcrSom,
  getElementById,
  getElementCenter,
  findElementByText,
};
