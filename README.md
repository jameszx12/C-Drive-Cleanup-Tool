# 🧹 C盘清理工具

**版本 v4.1.0** | 作者 zx

一个安全、高效的 Windows C 盘垃圾清理工具，配备现代化扁平设计与玻璃质感 UI、分类导航与智能扫描引擎，帮你快速释放磁盘空间。

![version](https://img.shields.io/badge/version-v4.1.0-blue)
![platform](https://img.shields.io/badge/platform-Windows-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## ✨ 功能特色

- **🪟 窗口缝隙毛玻璃**（v3.0.1 新增）
  系统级 Acrylic 模糊 + 内容面板保持不透明 → 窗口边距与卡片间隙透出柔和模糊背景，营造现代「缝隙玻璃」高级质感。设置项可开关，旧系统自动回退纯色。

- **🧭 分类导航侧边栏**
  全部项目 / 系统垃圾 / 浏览器 / 应用缓存 / 开发工具 / 游戏平台 / 媒体工具 / 云盘 / 驱动显卡 / 深度扫描 / 更新安装包，按分类快速过滤，实时显示各类文件数与体积。搜索框按名称/描述跨分类过滤。

- **🎨 现代扁平设计**
  统一线性图标（@tabler/icons 矢量源）+ 玻璃质感卡片 + iOS 风格半透明按钮 + 精致徽章 + 精确间距体系；明暗双主题 + 「跟随系统」（darkdetect 自动响应）。**选中卡片左侧强调条** + **扫描/清理进度条流动动画** + **Tooltip** + **Toast** 通知。

- **📂 二级目录精确选择**
  第三方应用深度清理、软件更新安装包支持展开二级目录，可逐项勾选/取消，支持全选、反选，清理粒度更自由。

- **📁 资源管理器一键定位**
  每个清理项（一级与二级）均提供「📂 打开」按钮，可直接在文件资源管理器中定位并打开对应文件夹或文件，方便核查。

- **📦 软件更新安装包清理**
  自动识别 AppData / ProgramData 中各大软件下载的更新安装包（`.exe` `.msi` `.msu` `.cab` `.msp`），排除小于 1MB 的小文件，按软件来源分组，清晰展示文件名、版本号、大小与路径。

- **⌨️ 键盘快捷**
  Enter / F5 启动扫描；Ctrl+A 全选；Ctrl+Shift+A 全不选；Tab 焦点导航带焦点环。

- **🖼️ 真实应用图标 + 矢量品牌图标**
  清理项优先显示已安装应用的真实图标（Chrome / Edge / 微信 / Steam 等），无则回退到 @tabler/icons 品牌线框图标（按分类着色），跨机器显示一致、零锯齿。

- **📊 清理统计实时准确**
  清理确认与结果显示均基于用户实际勾选的二级项目精确计算文件数和空间占用，一目了然。

- **⚡ 高性能不卡顿**
  扫描与清理在子线程中执行，UI 不卡顿；详情对话框通过分页、搜索与异步渲染保持丝滑。

- **🛡️ 安全边界明确**
  仅清理系统临时目录、应用缓存、日志、崩溃转储等垃圾文件，**绝不触碰**桌面、文档、下载、图片、视频、音乐等个人文件夹。

## 📁 目录结构

```
.
├── main.py                 入口与兼容导出（python main.py 启动）
├── config.py               配置：常量 / 主题 / 路径 / 用户设置 / 日志
├── rules.py                清理规则：垃圾类型分类 / 规则构建
├── engine.py               扫描与清理引擎（无 GUI 依赖，可独立测试）
├── icons.py                应用图标提取与内置图标加载
├── glass.py                Windows 毛玻璃背景（iOS 风格半透明）
├── particles.py            动画粒子内核（性能测试保留）
├── widgets.py              通用 UI 部件（字体 / 颜色 / 玻璃卡片工厂）
├── dialogs.py              详情对话框（文件夹归属 / 安装包 / 设置）
├── app.py                  主窗口 CleanerApp
├── tests/                  测试套件（selftest / 回归 / 性能 / 冒烟）
├── tools/                  开发工具（应用图标 / SVG 图标生成脚本）
├── run.bat                 源码一键运行（用 miniconda 环境，双击即可）
├── build.bat               一键打包脚本（所有打包命令已固化）
├── C盘清理工具.spec         PyInstaller 打包配置
├── icons/                  内置清理项图标（PNG + SVG 源文件）
├── app_icon.svg             应用图标源文件（SVG 矢量）
├── app_icon.ico             应用图标（多尺寸，打包时嵌入 exe）
├── app_icon.png             应用图标预览（256×256）
├── LICENSE                  MIT 许可证
└── CHANGELOG.md             完整版本历史
```

## 🚀 快速开始

### 运行已打包版本（推荐）
从 [Releases](../../releases) 下载 `C-Drive-Cleanup-Tool-v4.1.0.exe`（即 C盘清理工具 v4.1.0），双击运行。程序会请求管理员权限（因为需要清理系统目录），请点击「是」。首次运行若被 Windows SmartScreen 拦截，选择「仍要运行」即可（本工具无任何恶意行为）。

### 从源码运行
1. 双击 `run.bat`（使用本机 miniconda 环境，已带 tkinter + customtkinter）即可运行。
   或手动执行（需要带 tkinter 的 Python 3.10+，本机默认 python 无 tkinter）：
   ```bash
   D:\miniconda3\python.exe main.py
   ```
2. 需要以管理员权限运行（建议右键 `run.bat` → 以管理员身份运行）。

### 重新打包为 exe
修改源码后，双击 `build.bat` 即可自动打包，生成新的 `C盘清理工具.exe`。

## 🔧 自定义与迭代

程序已模块化，主要可修改文件及其职责：

- **清理规则**：`rules.py` 的 `build_rules()` 函数，可增删清理项与扫描路径。
- **扫描/清理逻辑**：`engine.py`（无 GUI 依赖，可直接 `python tests/selftest.py` 验证）。
- **界面信息**：`config.py` 的 `APP_NAME`、`AUTHOR`、`VERSION` 变量。
- **深度扫描范围**：`rules.py` 的扩展名、目录黑名单，控制「激进」程度。

修改后运行 `build.bat` 重新打包，或双击 `run.bat` 直接测试效果。

## 🛡️ 安全边界说明

本工具**仅清理**以下类别的垃圾文件：

- 系统临时目录：`C:\Windows\Temp`、`SoftwareDistribution`、`Prefetch` 等
- 用户临时目录：`%LocalAppData%\Temp`
- 回收站：`$Recycle.Bin`
- 各类应用缓存与日志：位于 `AppData`、`ProgramData` 下的 `cache`、`temp`、`logs` 等目录
- 特定扩展名垃圾：`*.log`、`*.tmp`、`*.bak`、`*.dmp`、`*.crdownload` 等

**绝不涉及**：桌面、文档、下载、图片、视频、音乐等个人文件目录。
每次清理前均有详细列表与空间统计，确认后才会执行，请放心使用。

## 📜 许可与声明

本工具基于 [MIT](LICENSE) 协议开源（© 2026 zx），供个人学习与日常维护使用。使用时请确认清理内容，因误操作或其他原因导致的数据丢失，开发者不承担任何责任。欢迎反馈问题与建议（Issues / PR）。

完整更新历史见 [CHANGELOG.md](CHANGELOG.md)。

---

如果觉得好用，请给个 ⭐！  
Made with ❤️ by zx
