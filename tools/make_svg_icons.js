// 清理项线性图标生成（Tabler SVG → 64px PNG，按分类配色着色）
// 覆盖全部规则 key：系统类用通用图标，第三方应用用品牌图标（brand-*）
// 依赖：node_modules 中的 sharp + @tabler/icons（位于受管 node 工作区）
// 运行：
//   NODE_PATH=C:/Users/zx/.workbuddy/binaries/node/workspace/node_modules \
//     C:/Users/zx/.workbuddy/binaries/node/versions/22.22.2/node.exe tools/make_svg_icons.js
//
// 产物：icons/<key>.png（64x64 透明 PNG）
//        icons/svg/<name>.svg（源文件留档）
'use strict';
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const ROOT = path.join(__dirname, '..');
const ICONS_DIR = path.join(ROOT, 'icons');
const SVG_SRC_DIR = path.join(ROOT, 'icons', 'svg');
const TABLER_DIR = path.join(process.env.NODE_PATH || '', '@tabler', 'icons', 'icons', 'outline');

const TARGET = 64;

// key -> (tabler 图标名, 图标颜色, 说明)
// 颜色与 widgets.rule_visual 的分类强调色保持一致：
//   系统 #60a5fa / 浏览器 #22d3a0 / 应用 #fbbf24 / 开发 #38bdf8 / 游戏 #a855f7
//   媒体 #f472b6 / 云盘 #06b6d4 / 驱动 #94a3b8 / 深度 #a78bfa / 安装包 #38bdf8
const C = {
  sys: '#60a5fa', browser: '#22d3a0', app: '#fbbf24', dev: '#38bdf8',
  game: '#a855f7', media: '#f472b6', cloud: '#06b6d4', driver: '#94a3b8',
  deep: '#a78bfa', update: '#38bdf8',
};
const MAP = {
  // ---- 系统类 ----
  win_temp:    ['brush', C.sys, '临时文件（清扫刷）'],
  user_temp:   ['brush', C.sys, '用户临时文件（清扫刷）'],
  prefetch:    ['gauge', C.sys, '预读取（仪表盘）'],
  wsus:        ['download', C.sys, 'Windows 更新缓存（下载）'],
  delivery:    ['package', C.sys, '更新交付（包裹）'],
  wer:         ['alert-triangle', C.sys, '错误报告（警示三角）'],
  winlogs:     ['file-text', C.sys, '系统日志（文本文件）'],
  crashdumps:  ['bug', C.sys, '崩溃转储（虫子）'],
  recycle:     ['recycle', C.sys, '回收站（循环箭头）'],
  thumb:       ['photo', C.sys, '缩略图（图片）'],
  // ---- 浏览器 ----
  chrome_cache:  ['brand-chrome', C.browser, 'Chrome'],
  edge_cache:    ['brand-edge', C.browser, 'Edge'],
  firefox_cache: ['brand-firefox', C.browser, 'Firefox'],
  opera_cache:   ['brand-opera', C.browser, 'Opera'],
  brave_cache:   ['shield', C.browser, 'Brave（盾牌）'],
  // ---- 通讯 / 协作 ----
  discord: ['brand-discord', C.app, 'Discord'],
  slack:   ['brand-slack', C.app, 'Slack'],
  teams:   ['video', C.app, 'Teams（视频）'],
  wechat:  ['brand-wechat', C.app, '微信'],
  // ---- 开发工具 ----
  vscode:         ['brand-vscode', C.dev, 'VS Code'],
  jetbrains:      ['code', C.dev, 'JetBrains'],
  npm_cache:      ['brand-npm', C.dev, 'npm'],
  pip_cache:      ['brand-python', C.dev, 'pip/Python'],
  android_studio: ['brand-android', C.dev, 'Android Studio'],
  // ---- 游戏平台 ----
  steam:     ['brand-steam', C.game, 'Steam'],
  epic:      ['device-gamepad', C.game, 'Epic'],
  ea_origin: ['planet', C.game, 'EA/Origin'],
  ubisoft:   ['snowflake', C.game, 'Ubisoft'],
  gog:       ['star', C.game, 'GOG'],
  battlenet: ['swords', C.game, 'Battle.net'],
  // ---- 媒体 / 设计 ----
  adobe_mediacache: ['brand-adobe', C.media, 'Adobe'],
  adobe_logs:       ['brand-adobe', C.media, 'Adobe'],
  spotify:          ['brand-spotify', C.media, 'Spotify'],
  obs:              ['camera', C.media, 'OBS'],
  // ---- 云盘 ----
  dropbox:       ['brand-dropbox', C.cloud, 'Dropbox'],
  baidu:         ['brand-baidu', C.cloud, '百度网盘'],
  onedrive_logs: ['cloud', C.cloud, 'OneDrive'],
  // ---- 驱动 / 显卡 ----
  nvidia: ['cpu', C.driver, 'NVIDIA'],
  amd:    ['brand-amd', C.driver, 'AMD'],
  intel:  ['cpu', C.driver, 'Intel'],
  // ---- 深度扫描 / 更新安装包 ----
  deep_apps:      ['radar', C.deep, '深度扫描（雷达）'],
  update_packages: ['package', C.update, '更新安装包'],
};

async function render(name, color) {
  const svgPath = path.join(TABLER_DIR, name + '.svg');
  if (!fs.existsSync(svgPath)) return null;
  const raw = fs.readFileSync(svgPath, 'utf8');
  const colored = raw.replace(/currentColor/g, color);
  return await sharp(Buffer.from(colored), { density: 300 })
    .resize(TARGET, TARGET, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png({ compressionLevel: 9 })
    .toBuffer();
}

(async () => {
  if (!fs.existsSync(SVG_SRC_DIR)) fs.mkdirSync(SVG_SRC_DIR, { recursive: true });
  let n = 0, fail = 0;
  for (const [key, [iconName, color, desc]] of Object.entries(MAP)) {
    try {
      const png = await render(iconName, color);
      if (!png) { console.log(`  ${key} MISSING ${iconName}`); fail++; continue; }
      fs.writeFileSync(path.join(ICONS_DIR, key + '.png'), png);
      // 源 SVG 留档（着色后），便于日后换色/换风格
      const raw = fs.readFileSync(path.join(TABLER_DIR, iconName + '.svg'), 'utf8');
      fs.writeFileSync(path.join(SVG_SRC_DIR, iconName + '.svg'),
                       raw.replace(/currentColor/g, color));
      n++;
    } catch (e) {
      console.log(`  ${key} FAIL: ${e.message.slice(0, 90)}`);
      fail++;
    }
  }
  console.log(`rule icons done: ${n} files, ${fail} failed`);
})();
