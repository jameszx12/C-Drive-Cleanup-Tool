// UI 线框图标生成（Tabler SVG → 24/20px PNG，明暗双变体）
// 用于：按钮 / 侧边栏 / 统计卡 / 空状态 —— 统一现代扁平线性图标，替换 emoji 与字符符号
// 运行：
//   NODE_PATH=C:/Users/zx/.workbuddy/binaries/node/workspace/node_modules \
//     C:/Users/zx/.workbuddy/binaries/node/versions/22.22.2/node.exe tools/make_ui_icons.js
//
// 产物：icons/ui/{d|l}_{name}_{size}.png
//   d_ = 深色主题用（浅灰蓝 #a5b3cb）
//   l_ = 浅色主题用（深蓝灰 #53617a）
'use strict';
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const ROOT = path.join(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'icons', 'ui');
// 图标搜索路径（按优先级）：
//   1) 本地裸装（项目内 node_modules，可能被 tabler v3 裁剪过）
//   2) 受管工作区 node_modules
//   3) tools/cache 下从 unpkg 补下的缺失图标
const SEARCH_DIRS = [
  path.join(ROOT, 'node_modules', '@tabler', 'icons', 'icons', 'outline'),
  path.join(process.env.NODE_PATH || '', '@tabler', 'icons', 'icons', 'outline'),
  path.join(__dirname, 'cache'),
].filter(p => p && !p.startsWith(path.join('@tabler')));
const findSvg = (name) => {
  for (const dir of SEARCH_DIRS) {
    const p = path.join(dir, name + '.svg');
    if (fs.existsSync(p)) return p;
  }
  return null;
};

const SIZES = [20, 24];
// 颜色取自 config.py 主题令牌的中间调和色（两种主题下都可辨识）
const VARIANTS = { d: '#a5b3cb', l: '#53617a' };

// map：name -> tabler 图标名
const MAP = {
  scan: 'search',          // 开始扫描
  search: 'search',        // 搜索框前置图标
  clean: 'trash',          // 清理选中
  cancel: 'x',             // 取消
  sel_all_on: 'square-check', // 全选（已全选态）
  sel_all_off: 'square',   // 全选（未全选态）
  sel_none_on: 'square-x', // 全不选（有选中态）
  sel_none_off: 'square',  // 全不选（已清空态）
  settings: 'settings',    // 设置
  power: 'power',          // 退出
  sun: 'sun',              // 亮色
  moon: 'moon',            // 暗色
  sun_moon: 'sun-moon',    // 跟随系统（半日月）
  half_circle: 'circle-half-2', // 半圆（旧备用）
  folder: 'folder-open',   // 打开目录
  pkg: 'package',          // 查看安装包
  prev: 'chevron-left',    // 上一页
  next: 'chevron-right',   // 下一页
  search_clear: 'x',       // 清除搜索
  invert: 'arrows-exchange', // 反选
  expand: 'chevrons-down',   // 全部展开
  collapse: 'chevrons-up',   // 全部收起
  file: 'file',            // 统计-文件
  drive: 'database',       // 统计-空间
  nav_all: 'layout-grid',  // 侧边栏-全部
  nav_system: 'brush',     // 侧边栏-系统
  nav_browser: 'browser',  // 侧边栏-浏览器
  nav_app: 'apps',         // 侧边栏-应用
  nav_dev: 'code',         // 侧边栏-开发
  nav_game: 'device-gamepad', // 侧边栏-游戏
  nav_media: 'palette',    // 侧边栏-媒体
  nav_cloud: 'cloud',      // 侧边栏-云盘
  nav_driver: 'cpu',       // 侧边栏-驱动
  nav_deep: 'radar',       // 侧边栏-深度
  nav_update: 'package',   // 侧边栏-安装包
  empty: 'sparkles',       // 空状态
  safe: 'shield-check',    // 安全提示
  check: 'circle-check',   // 完成
  trash: 'trash',          // 清理（别名）
  refresh: 'refresh',      // 重新扫描
  pin: 'map-pin',          // 定位
  clock: 'clock',          // 时间
};

(async () => {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
  let n = 0, fail = 0;
  for (const [key, iconName] of Object.entries(MAP)) {
    const svgPath = findSvg(iconName);
    if (!svgPath) { console.log(`  MISSING ${iconName}`); fail++; continue; }
    const raw = fs.readFileSync(svgPath, 'utf8');
    for (const [v, color] of Object.entries(VARIANTS)) {
      for (const size of SIZES) {
        try {
          const colored = raw.replace(/currentColor/g, color);
          const png = await sharp(Buffer.from(colored), { density: 300 })
            .resize(size, size, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
            .png({ compressionLevel: 9 })
            .toBuffer();
          fs.writeFileSync(path.join(OUT_DIR, `${v}_${key}_${size}.png`), png);
          n++;
        } catch (e) {
          console.log(`  ${key}[${v}@${size}] FAIL: ${e.message.slice(0, 80)}`);
          fail++;
        }
      }
    }
  }
  console.log(`ui icons done: ${n} files, ${fail} failed`);
})();
