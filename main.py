# -*- coding: utf-8 -*-
"""
C盘垃圾清理工具  v2.3.2
作者: zx
清理范围：
  - 系统垃圾（临时文件 / 回收站 / 预读取 / 更新缓存 / 缩略图 / 错误报告 / 系统日志）
  - 第三方应用垃圾（浏览器 / 通讯 / 开发工具 / 游戏平台 / 媒体设计 / 云盘 / 驱动 的缓存、临时、日志、升级残留）
  - 深度扫描引擎：遍历 AppData / ProgramData 中的 cache/temp/logs 类目录与已知垃圾扩展名文件
  - 软件更新安装包扫描：识别各软件下载的更新安装包（.exe/.msi/.cab 等），可按软件来源展开查看文件名/版本/大小
安全边界：仅处理系统目录与 AppData/ProgramData 中的缓存/临时/日志，绝不删除个人文档/桌面/下载/图片/视频。
扫描与清理均在子线程中进行，UI 不卡顿。

v2.3.2 更新（二级目录选择 + 资源管理器打开）：
  - 二级目录选择：在「第三方应用深度清理」和「软件更新安装包」详情对话框中，
    每个文件夹/安装包均可勾选/取消，与一级目录选择行为一致
    （含全选/反选、默认全选、清理时仅清理选中项）
  - 资源管理器打开：每个清理项（一级与二级）操作区新增「📂 打开」按钮，
    点击后在文件资源管理器中定位并打开对应文件/文件夹路径
    （文件夹直接打开目录，文件用 explorer /select, 定位）

v2.3.1 更新（新增软件更新安装包清理）：
  - 新增「软件更新安装包」扫描模块：识别各软件在 AppData/ProgramData 中下载的更新安装包
    （.exe / .msi / .msu / .cab / .msp），排除 <1MB 的小文件避免误报
  - 按软件来源分组，提供可展开/收起的详情对话框，查看每个安装包的：
      软件来源名 / 安装包文件名 / 版本号 / 大小 / 路径
  - 版本号从文件名自动解析（正则匹配 x.y.z 形式）
  - 交互方式与「第三方应用深度清理」完全一致：主界面卡片 + 「📦 查看安装包」按钮 + 毛玻璃对话框
  - 复用分页 + 搜索 + 异步渲染 + 轻量粒子背景，体验统一

v2.3.0 更新（UI 视觉重做）：
  - 全新视觉系统：深邃渐变背景 + 毛玻璃风格卡片 + 现代化字体层级与配色
  - 新增动画粒子背景层（Canvas 实现，~45 个发光粒子缓慢上浮 + 闪烁）
  - 新增交互反馈粒子爆发：点击「扫描垃圾」/「清理选中」时从按钮位置迸射粒子
  - 卡片采用毛玻璃质感（柔和边框 + 悬停高亮 + 大圆角），整体更现代精致
  - 优化空状态、状态栏与进度条（带发光强调色）
  - 性能保障：粒子数量上限 + coords 原地更新（非 delete/recreate），30fps 单循环，
    最小化不阻塞主线程；扫描/清理仍在子线程
"""
import os
import sys
import re
import math
import glob
import random
import subprocess
import threading
import tkinter as tk
import tkinter.messagebox as mb
import customtkinter as ctk

APP_NAME = "C盘垃圾清理工具"
AUTHOR = "zx"
VERSION = "v2.3.3"

# ---------- 视觉系统 ----------
FONT_FAMILY = "Microsoft YaHei UI"   # Windows 系统内置中文字体，清晰锐利
MONO_FAMILY = "Consolas"              # 等宽字体，用于路径显示

# Dark 主题配色（v2.3.0 全新调色：更深邃的底色 + 更鲜活的强调色）
C_BG          = "#0d1018"   # 窗口底色（最深，作为渐变起点）
C_BG_TOP      = "#0d1018"   # 渐变顶部
C_BG_MID      = "#161a2e"   # 渐变中部（蓝紫调）
C_BG_BOT      = "#1c1430"   # 渐变底部（深紫调）

# 毛玻璃面板色：在深色渐变上呈现“磨砂玻璃”质感
C_GLASS       = "#161b2b"   # 玻璃卡片底色
C_GLASS_HOV   = "#1d2438"   # 玻璃卡片悬停
C_GLASS_2     = "#1a2033"   # 次级玻璃面板（标题栏 / 状态栏）
C_GLASS_BORDER = "#2f3a55"  # 玻璃边框（柔和蓝灰）
C_GLASS_BORDER_HL = "#4a5878"  # 玻璃高光边框
C_PANEL        = "#111827"   # 数据仪表盘与分类标签的内层面板
C_PANEL_SOFT   = "#202a42"   # 内层面板的备用高亮色

C_PRIMARY     = "#5b8cff"   # 主操作色（更鲜亮）
C_PRIMARY_HOV = "#3d6ef0"
C_PRIMARY_GLOW = "#7aa2ff"
C_SUCCESS     = "#22d3a0"   # 绿色 - 释放空间 / 通过
C_WARN        = "#fbbf24"   # 橙色 - 清理按钮
C_WARN_HOV    = "#f59e0b"
C_DANGER      = "#f87171"
C_TEXT        = "#f1f5f9"   # 主文字（更亮）
C_TEXT_DIM    = "#94a3b8"   # 次文字
C_TEXT_FAINT  = "#64748b"   # 弱文字

# 主题令牌集中管理：切换时重建界面，以保证 Canvas、卡片和弹窗使用同一套配色。
THEMES = {
    "dark": {
        "C_BG": "#0d1018", "C_BG_TOP": "#0d1018", "C_BG_MID": "#161a2e", "C_BG_BOT": "#1c1430",
        "C_GLASS": "#161b2b", "C_GLASS_HOV": "#1d2438", "C_GLASS_2": "#1a2033",
        "C_GLASS_BORDER": "#2f3a55", "C_GLASS_BORDER_HL": "#4a5878", "C_PANEL": "#111827", "C_PANEL_SOFT": "#202a42",
        "C_PRIMARY": "#5b8cff", "C_PRIMARY_HOV": "#3d6ef0", "C_PRIMARY_GLOW": "#7aa2ff",
        "C_SUCCESS": "#22d3a0", "C_WARN": "#fbbf24", "C_WARN_HOV": "#f59e0b", "C_DANGER": "#f87171",
        "C_TEXT": "#f1f5f9", "C_TEXT_DIM": "#94a3b8", "C_TEXT_FAINT": "#64748b",
    },
    "light": {
        "C_BG": "#eef3fb", "C_BG_TOP": "#f8fbff", "C_BG_MID": "#edf4ff", "C_BG_BOT": "#e7efff",
        "C_GLASS": "#ffffff", "C_GLASS_HOV": "#f4f8ff", "C_GLASS_2": "#f9fbff",
        "C_GLASS_BORDER": "#d7e1f2", "C_GLASS_BORDER_HL": "#b6c8e6", "C_PANEL": "#f3f7fd", "C_PANEL_SOFT": "#e8f0ff",
        "C_PRIMARY": "#3867d6", "C_PRIMARY_HOV": "#2b55b7", "C_PRIMARY_GLOW": "#5b84df",
        "C_SUCCESS": "#0f9d73", "C_WARN": "#d88906", "C_WARN_HOV": "#b96e00", "C_DANGER": "#d94c4c",
        "C_TEXT": "#18243a", "C_TEXT_DIM": "#5d6b82", "C_TEXT_FAINT": "#8491a6",
    },
}


def apply_theme(theme_name):
    """应用主题色令牌；调用方负责重建已创建的控件。"""
    if theme_name not in THEMES:
        raise ValueError(f"Unknown theme: {theme_name}")
    globals().update(THEMES[theme_name])

# 粒子可选色板
PARTICLE_COLORS = ["#5b8cff", "#8b5cf6", "#22d3a0", "#a855f7", "#06b6d4", "#0ea5e9"]


def rule_visual(rule):
    """为清理类别提供一致的图标与强调色。"""
    if rule.get("type") == "deep":
        return "◈", "#a78bfa", "深度扫描"
    if rule.get("type") == "update":
        return "↓", "#38bdf8", "安装包"
    key = rule.get("key", "")
    if key in {"recycle", "prefetch", "wsus", "delivery", "thumb", "wer", "winlogs", "crashdumps", "win_temp"}:
        return "▣", "#60a5fa", "系统空间"
    if any(x in key for x in ("chrome", "edge", "firefox", "opera", "browser")):
        return "◎", "#22d3a0", "浏览器"
    return "◇", "#fbbf24", "应用缓存"


def fnt(size, weight="normal"):
    """统一字体工厂，确保全程序字体一致。"""
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def mono_fnt(size=11):
    return ctk.CTkFont(family=MONO_FAMILY, size=size)


# ---------- 垃圾类型分类 ----------
# 目录名 -> 垃圾类型
FOLDER_NAME_TO_TYPE = {
    "cache": "缓存", "caches": "缓存", "cached": "缓存",
    "gpucache": "GPU缓存",
    "code cache": "代码缓存",
    "shadercache": "着色器缓存", "dxcache": "DX缓存", "glcache": "GL缓存",
    "mediacache": "媒体缓存", "mediacachefiles": "媒体缓存",
    "webcache": "网页缓存", "web-cache": "网页缓存", "http cache": "HTTP缓存",
    "appcache": "应用缓存", "depotcache": "Depot缓存",
    "temp": "临时文件", "tmp": "临时文件", "temporary": "临时文件", "temps": "临时文件",
    "logs": "日志", "log": "日志",
    "crashpad": "崩溃数据", "crashreports": "崩溃报告",
    "crashes": "崩溃数据", "crashdumps": "崩溃转储",
    "thumbnails": "缩略图",
    "service worker": "Service Worker",
    "blobstorage": "Blob存储", "blob_storage": "Blob存储",
    "session storage": "会话存储",
    "databases": "数据库",
    "dvdcss": "DVD解密缓存",
    ".dropbox.cache": "云盘缓存",
    "browser-profile": "浏览器配置", "browserprofile": "浏览器配置",
}

# 扩展名 -> 垃圾类型（文件级匹配的归类）
EXT_TO_TYPE = {
    ".log": "日志文件",
    ".tmp": "临时文件", ".temp": "临时文件",
    ".bak": "备份文件", ".old": "备份文件",
    ".cache": "缓存文件",
    ".crdownload": "下载残留", ".part": "下载残留", ".download": "下载残留",
    ".dmp": "崩溃转储", ".etl": "事件追踪日志",
    ".swp": "交换文件", ".swo": "交换文件",
    ".~": "临时文件",
}

# 垃圾类型 -> 徽章颜色
TYPE_COLORS = {
    "缓存": "#5b8cff", "缓存文件": "#5b8cff", "应用缓存": "#5b8cff", "Depot缓存": "#5b8cff",
    "GPU缓存": "#8b5cf6", "代码缓存": "#6366f1",
    "着色器缓存": "#a855f7", "DX缓存": "#9333ea", "GL缓存": "#9333ea",
    "媒体缓存": "#06b6d4", "网页缓存": "#0ea5e9", "HTTP缓存": "#0ea5e9",
    "云盘缓存": "#06b6d4", "DVD解密缓存": "#5b8cff", "浏览器配置": "#0ea5e9",
    "临时文件": "#fbbf24", "下载残留": "#fbbf24", "交换文件": "#fbbf24", "备份文件": "#fbbf24",
    "日志": "#22d3a0", "日志文件": "#22d3a0", "事件追踪日志": "#22d3a0",
    "崩溃数据": "#f87171", "崩溃报告": "#f87171", "崩溃转储": "#f87171",
    "缩略图": "#14b8a6",
    "Service Worker": "#ec4899",
    "Blob存储": "#f97316",
    "会话存储": "#84cc16",
    "数据库": "#eab308",
    "其他": "#64748b",
}


def classify_junk_type(dirpath_segs, ext):
    """根据文件夹路径段（小写列表）与文件扩展名判断垃圾类型。"""
    for seg in dirpath_segs:
        if seg in FOLDER_NAME_TO_TYPE:
            return FOLDER_NAME_TO_TYPE[seg]
    if ext and ext in EXT_TO_TYPE:
        return EXT_TO_TYPE[ext]
    return "其他"


# ---------- 工具函数 ----------
def fmt_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n/1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n/1024/1024:.1f} MB"
    return f"{n/1024/1024/1024:.2f} GB"


def env(name, default=""):
    return os.environ.get(name, default)


LOCAL = env("LOCALAPPDATA", "")
APP = env("APPDATA", "")
PF = env("PROGRAMFILES", r"C:\Program Files")
PFX = env("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
PD = env("PROGRAMDATA", r"C:\ProgramData")
HOME = env("USERPROFILE", r"C:\Users")

# ---------- 深度扫描引擎配置 ----------
JUNK_FOLDER_NAMES = {
    "cache", "caches", "cached", "temp", "tmp", "temporary", "temps",
    "logs", "log", "crashpad", "crashreports", "crashes", "crashdumps",
    "gpucache", "code cache", "service worker", "shadercache", "dxcache",
    "glcache", "mediacache", "mediacachefiles", "thumbnails", "webcache",
    "web-cache", "http cache", "blobstorage", "blob_storage",
    "session storage", "databases", "depotcache", "appcache",
    "dvdcss", ".dropbox.cache", "browser-profile", "browserprofile",
}
JUNK_EXTENSIONS = {
    ".log", ".tmp", ".temp", ".bak", ".old", ".cache", ".crdownload",
    ".part", ".download", ".dmp", ".etl", ".swp", ".swo", ".~",
}
SKIP_SEGMENTS = {
    "node_modules", ".git", "obj", "bin", "packages", "site-packages",
    "vendor", ".venv", "venv", "user data", "users", "profiles", "profile",
    "documents", "desktop", "downloads", "pictures", "music", "videos",
    "mail", "contacts", "onedrive", "filestorage", "config", "preferences",
    "resources", "assets", "data", "wwwroot", "public", "src", "lib",
}
DEEP_CAP = 400000
APP_FOLDER_NAME_MAP = {
    "discord": "Discord", "slack": "Slack", "code": "Visual Studio Code",
    "jetbrains": "JetBrains IDE", "spotify": "Spotify", "obs-studio": "OBS Studio",
    "epicgameslauncher": "Epic Games Launcher", "origin": "EA / Origin",
    "battle.net": "Battle.net", "ubisoft game launcher": "Ubisoft Connect",
    "gog.com": "GOG Galaxy", "bravesoftware": "Brave Browser",
    "google": "Google Chrome / Google 应用", "mozilla": "Mozilla Firefox",
    "opera software": "Opera", "adobe": "Adobe", "baidu": "百度网盘",
    "dropbox": "Dropbox", "nvidia": "NVIDIA", "amd": "AMD Software", "intel": "Intel",
}

# ---------- 软件更新安装包识别配置 ----------
# 安装包扩展名
INSTALLER_EXTENSIONS = {".exe", ".msi", ".msu", ".cab", ".msp"}
# 更新/安装包类目录名（命中后其中的安装包文件纳入扫描）
UPDATE_FOLDER_NAMES = {
    "update", "updates", "updater", "download", "downloads",
    "installer", "installers", "setup", "setupfiles",
    "packages", "distribution", "redist", "redistributable",
    "webinstall", "websetup", "bootstrapper",
}
# 文件名关键词：命中后即使不在 update 目录也视为安装包（提升召回）
INSTALLER_NAME_KEYWORDS = (
    "setup", "install", "update", "upgrade", "patch",
    "redist", "bootstrapper", "webinstall", "client",
)
# 更新安装包扫描的剪枝段（比 deep 宽松：允许 download/downloads/installer 等，因为
# 扫描根目录仅限 AppData/ProgramData，不会触及个人 Downloads/Desktop）
UPDATE_SKIP_SEGMENTS = {
    "node_modules", ".git", "obj", "bin", "packages", "site-packages",
    "vendor", ".venv", "venv", "src", "lib", "resources", "assets",
    "wwwroot", "public", "cache", "caches", "temp", "tmp", "logs",
    "service worker", "gpucache", "shadercache",
}
# 安装包最小体积阈值：<1MB 的不纳入（避免把小工具/配置当安装包）
INSTALLER_MIN_SIZE = 1024 * 1024

# ---------- 规则构建 ----------
def _glob(patterns):
    out = []
    for p in patterns:
        if "*" in p or "?" in p:
            out.extend(glob.glob(p))
        else:
            out.append(p)
    seen = set()
    res = []
    for p in out:
        if p and p not in seen and os.path.exists(p):
            seen.add(p)
            res.append(p)
    return res


def build_rules():
    R = []

    # ===== 系统垃圾 =====
    R.append(dict(key="win_temp", name="Windows 临时文件", desc="C:\\Windows\\Temp 系统临时文件",
                  type="path", paths=[r"C:\Windows\Temp"], recursive=True, pattern="*"))
    R.append(dict(key="user_temp", name="用户临时文件", desc="当前用户 Temp 目录临时文件",
                  type="path", paths=[os.path.join(LOCAL, "Temp")], recursive=True, pattern="*"))
    R.append(dict(key="recycle", name="回收站", desc="C 盘回收站中已删除的文件",
                  type="path", paths=[r"C:\$Recycle.Bin"], recursive=True, pattern="*"))
    R.append(dict(key="prefetch", name="预读取文件", desc="C:\\Windows\\Prefetch 加速缓存",
                  type="path", paths=[r"C:\Windows\Prefetch"], recursive=False, pattern="*"))
    R.append(dict(key="wsus", name="Windows 更新缓存", desc="SoftwareDistribution\\Download 更新备份",
                  type="path", paths=[r"C:\Windows\SoftwareDistribution\Download"], recursive=True, pattern="*"))
    R.append(dict(key="delivery", name="传递优化缓存", desc="DeliveryOptimization 分发缓存",
                  type="path", paths=[r"C:\Windows\SoftwareDistribution\DeliveryOptimization\Cache"], recursive=True, pattern="*"))
    R.append(dict(key="thumb", name="缩略图缓存", desc="资源管理器缩略图数据库 thumbcache_*.db",
                  type="path", paths=[os.path.join(LOCAL, "Microsoft", "Windows", "Explorer")], recursive=False, pattern="thumbcache_*.db"))
    R.append(dict(key="wer", name="系统错误报告", desc="Windows Error Reporting 错误转储",
                  type="path", paths=[os.path.join(LOCAL, "Microsoft", "Windows", "WER")], recursive=True, pattern="*"))
    R.append(dict(key="winlogs", name="Windows 系统日志缓存", desc="C:\\Windows\\Logs 下的 CBS/DISM/更新日志",
                  type="path", paths=[r"C:\Windows\Logs"], recursive=True, pattern="*"))
    R.append(dict(key="crashdumps", name="系统崩溃转储", desc="AppData 下的用户态崩溃转储 .dmp",
                  type="path", paths=[os.path.join(LOCAL, "CrashDumps")], recursive=True, pattern="*"))

    # ===== 浏览器 =====
    chrome_base = os.path.join(LOCAL, "Google", "Chrome", "User Data", "Default")
    edge_base = os.path.join(LOCAL, "Microsoft", "Edge", "User Data", "Default")
    R.append(dict(key="chrome_cache", name="Chrome 浏览器缓存", desc="Google Chrome 各类缓存与 Service Worker",
                  type="path", paths=_glob([os.path.join(chrome_base, x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Media Cache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="edge_cache", name="Edge 浏览器缓存", desc="Microsoft Edge 各类缓存与 Service Worker",
                  type="path", paths=_glob([os.path.join(edge_base, x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Media Cache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="firefox_cache", name="Firefox 浏览器缓存", desc="Mozilla Firefox 缓存与缩略图",
                  type="path", paths=_glob([
                      os.path.join(APP, "Mozilla", "Firefox", "Profiles", "*", "cache2"),
                      os.path.join(APP, "Mozilla", "Firefox", "Profiles", "*", "startupCache"),
                      os.path.join(APP, "Mozilla", "Firefox", "Profiles", "*", "thumbnails")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="opera_cache", name="Opera 浏览器缓存", desc="Opera Stable 缓存",
                  type="path", paths=_glob([os.path.join(APP, "Opera Software", "Opera Stable", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "Media Cache"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="brave_cache", name="Brave 浏览器缓存", desc="Brave Browser 各类缓存",
                  type="path", paths=_glob([os.path.join(LOCAL, "BraveSoftware", "Brave-Browser", "User Data", "Default", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "Media Cache"]]),
                  recursive=True, pattern="*"))

    # ===== 通讯 / 协作 =====
    R.append(dict(key="discord", name="Discord 缓存", desc="Discord 缓存 / GPUCache / Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "discord", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="slack", name="Slack 缓存", desc="Slack 缓存与 Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "Slack", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="teams", name="Microsoft Teams 缓存", desc="Teams 缓存 / 临时 / Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "Microsoft", "Teams", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "tmp"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="wechat", name="微信缓存/临时", desc="WeChat Files 下的 Cache/Temp/Thumb（不含聊天文件）",
                  type="path", paths=_glob([
                      os.path.join(HOME, "Documents", "WeChat Files", "*", "FileStorage", "Cache"),
                      os.path.join(HOME, "Documents", "WeChat Files", "*", "FileStorage", "Temp"),
                      os.path.join(HOME, "Documents", "WeChat Files", "*", "FileStorage", "Thumb")]),
                  recursive=True, pattern="*"))

    # ===== 开发工具 =====
    R.append(dict(key="vscode", name="VS Code 缓存/日志", desc="Visual Studio Code 缓存、日志与 Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "Code", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "CachedData", "logs", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="jetbrains", name="JetBrains IDE 缓存", desc="IDEA/PyCharm/WebStorm 等缓存、日志、临时",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "JetBrains", "*", "caches"),
                      os.path.join(LOCAL, "JetBrains", "*", "log"),
                      os.path.join(LOCAL, "JetBrains", "*", "tmp")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="npm_cache", name="npm 缓存", desc="Node.js npm 全局缓存",
                  type="path", paths=[os.path.join(APP, "npm-cache")], recursive=True, pattern="*"))
    R.append(dict(key="pip_cache", name="pip 缓存", desc="Python pip 下载缓存",
                  type="path", paths=[os.path.join(LOCAL, "pip", "Cache")], recursive=True, pattern="*"))
    R.append(dict(key="android_studio", name="Android Studio 缓存", desc="Android Studio 系统缓存与日志",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "Google", "AndroidStudio*", "system", "caches"),
                      os.path.join(LOCAL, "Google", "AndroidStudio*", "system", "log"),
                      os.path.join(LOCAL, "Google", "AndroidStudio*", "system", "tmp")]),
                  recursive=True, pattern="*"))

    # ===== 游戏平台 =====
    steam_paths = []
    for base in (PF, PFX, LOCAL):
        sp = os.path.join(base, "Steam")
        if os.path.isdir(sp):
            steam_paths += [os.path.join(sp, x) for x in ("downloads", "appcache", "logs", "tmp")]
    R.append(dict(key="steam", name="Steam 下载/更新缓存", desc="Steam 下载缓存、appcache、日志、临时",
                  type="path", paths=_glob(steam_paths), recursive=True, pattern="*"))
    R.append(dict(key="epic", name="Epic 游戏平台缓存", desc="EpicGamesLauncher 日志/崩溃/webcache",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "EpicGamesLauncher", "Saved", "Logs"),
                      os.path.join(LOCAL, "EpicGamesLauncher", "Saved", "Crashes"),
                      os.path.join(LOCAL, "EpicGamesLauncher", "Saved", "webcache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="ea_origin", name="EA / Origin 缓存", desc="Origin 日志与缓存",
                  type="path", paths=_glob([os.path.join(APP, "Origin", "Logs"), os.path.join(LOCAL, "Origin")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="ubisoft", name="Ubisoft Connect 缓存", desc="Ubisoft Game Launcher 缓存/日志/临时",
                  type="path", paths=_glob([os.path.join(LOCAL, "Ubisoft Game Launcher", x) for x in
                      ("cache", "logs", "temp")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="gog", name="GOG Galaxy 缓存", desc="GOG.com Galaxy 缓存与日志",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "GOG.com", "Galaxy", "Cache"),
                      os.path.join(PD, "GOG.com", "Galaxy", "Logs")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="battlenet", name="战网 Battle.net 缓存", desc="Battle.net 缓存与日志",
                  type="path", paths=_glob([
                      os.path.join(APP, "Battle.net", "Cache"),
                      os.path.join(PD, "Battle.net", "Cache"),
                      os.path.join(PD, "Battle.net", "Logs")]),
                  recursive=True, pattern="*"))

    # ===== 媒体 / 设计 =====
    R.append(dict(key="adobe_mediacache", name="Adobe 媒体缓存", desc="Adobe Common 媒体缓存/峰值文件（常达数 GB）",
                  type="path", paths=_glob([
                      os.path.join(APP, "Adobe", "Common", "Media Cache*"),
                      os.path.join(LOCAL, "Adobe", "Common", "Media Cache*")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="adobe_logs", name="Adobe 日志缓存", desc="Adobe 本地日志与临时",
                  type="path", paths=_glob([os.path.join(LOCAL, "Adobe")]), recursive=True, pattern="*"))
    R.append(dict(key="spotify", name="Spotify 日志", desc="Spotify 日志与浏览器缓存",
                  type="path", paths=_glob([os.path.join(LOCAL, "Spotify", "Logs"),
                                            os.path.join(LOCAL, "Spotify", "Browser-profile", "Cache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="obs", name="OBS Studio 缓存", desc="OBS 日志与临时",
                  type="path", paths=_glob([os.path.join(APP, "obs-studio")]), recursive=True, pattern="*"))

    # ===== 云盘 =====
    R.append(dict(key="dropbox", name="Dropbox 缓存", desc=".dropbox.cache 与日志",
                  type="path", paths=_glob([os.path.join(LOCAL, ".dropbox.cache"), os.path.join(LOCAL, "Dropbox", "logs")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="baidu", name="百度网盘缓存", desc="BaiduNetdisk 缓存/日志/webcache",
                  type="path", paths=_glob([os.path.join(LOCAL, "baidu", "BaiduNetdisk", x) for x in
                      ("cache", "logs", "webcache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="onedrive_logs", name="OneDrive 日志", desc="Microsoft OneDrive 日志",
                  type="path", paths=_glob([os.path.join(LOCAL, "Microsoft", "OneDrive", "logs")]),
                  recursive=True, pattern="*"))

    # ===== 驱动 / 显卡 =====
    R.append(dict(key="nvidia", name="NVIDIA 着色器缓存", desc="NVIDIA DXCache / GLCache 着色器缓存",
                  type="path", paths=_glob([os.path.join(LOCAL, "NVIDIA", x) for x in ("DXCache", "GLCache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="amd", name="AMD 着色器缓存", desc="AMD GLCache / DXCache",
                  type="path", paths=_glob([os.path.join(LOCAL, "AMD", "GLCache"), os.path.join(LOCAL, "AMD", "DXCache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="intel", name="Intel 着色器缓存", desc="Intel ShaderCache",
                  type="path", paths=_glob([os.path.join(LOCAL, "Intel", "ShaderCache")]),
                  recursive=True, pattern="*"))

    # ===== 深度扫描：第三方应用残留 =====
    R.append(dict(key="deep_apps", name="第三方应用深度清理（激进）",
                  desc="遍历 AppData/ProgramData 中的 cache/temp/logs 目录与 .log/.tmp/.bak/.dmp 等垃圾文件",
                  type="deep", roots=[p for p in (LOCAL, APP, PD) if p and os.path.isdir(p)],
                  recursive=True, pattern="*"))

    # ===== 软件更新安装包 =====
    R.append(dict(key="update_packages", name="软件更新安装包",
                  desc="扫描各软件下载的更新安装包（.exe/.msi/.cab 等），可按软件来源展开查看文件名/版本/大小",
                  type="update", roots=[p for p in (LOCAL, APP, PD) if p and os.path.isdir(p)],
                  recursive=True, pattern="*"))

    R = [r for r in R if (r.get("paths") or r.get("roots"))]
    return R

# ---------- 扫描 / 清理核心 ----------
def scan_path_rule(rule):
    count = 0
    size = 0
    files = []
    for base in rule["paths"]:
        if not base or not os.path.exists(base):
            continue
        try:
            if rule["recursive"]:
                for root, dirs, fnames in os.walk(base, onerror=lambda e: None):
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            continue
                        count += 1
                        size += sz
                        files.append((fp, sz))
            else:
                pat = rule["pattern"]
                for fn in os.listdir(base):
                    if pat != "*" and not fn.lower().startswith(pat.replace("*", "").lower()):
                        continue
                    fp = os.path.join(base, fn)
                    if os.path.isfile(fp):
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            continue
                        count += 1
                        size += sz
                        files.append((fp, sz))
        except (OSError, PermissionError):
            continue
    return count, size, files


def app_name_for_folder(folder, scan_root):
    """将深度扫描命中的目录归属到其 AppData/ProgramData 应用目录。"""
    try:
        relative = os.path.relpath(folder, scan_root)
    except ValueError:
        return "第三方应用（路径无法识别）"
    top_level = relative.split(os.sep, 1)[0]
    return APP_FOLDER_NAME_MAP.get(top_level.lower(), f"第三方应用（{top_level}）")


def scan_deep_rule(rule):
    count = 0
    size = 0
    files = []
    # {清理文件夹路径: {app, count, size, types(set)}}，用于在界面上说明文件夹归属与垃圾类型。
    folder_summaries = {}
    capped = False
    for root in rule["roots"]:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            # 剪枝：跳过受保护目录段，提升速度并保护个人数据
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_SEGMENTS]
            segs = [s.lower() for s in dirpath.split(os.sep)]
            in_junk = any(seg in JUNK_FOLDER_NAMES for seg in segs)
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                ext = os.path.splitext(fn)[1].lower()
                take = in_junk or (ext in JUNK_EXTENSIONS)
                if not take:
                    continue
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                count += 1
                size += sz
                summary = folder_summaries.setdefault(
                    dirpath,
                    {"app": app_name_for_folder(dirpath, root),
                     "count": 0, "size": 0, "types": set()},
                )
                summary["count"] += 1
                summary["size"] += sz
                # 归类垃圾类型
                summary["types"].add(classify_junk_type(segs, ext))
                if not capped:
                    files.append((fp, sz))
                    if len(files) >= DEEP_CAP:
                        capped = True
    rule["_deep_folders"] = folder_summaries
    return count, size, files


# ---------- 软件更新安装包扫描 ----------
_VERSION_RE = re.compile(r'(\d+\.\d+(?:\.\d+){1,2})')

def _parse_version(filename):
    """从文件名尝试解析版本号（匹配 x.y.z 或 x.y.z.w 形式）。"""
    m = _VERSION_RE.search(filename)
    return m.group(1) if m else "—"


def _looks_like_installer(filename):
    """文件名是否包含安装包相关关键词（用于目录名不命中时的补充召回）。"""
    fn = filename.lower()
    return any(k in fn for k in INSTALLER_NAME_KEYWORDS)


def scan_update_packages_rule(rule):
    """
    扫描软件更新安装包。

    纳入条件（同时满足）：
      1) 文件扩展名在 INSTALLER_EXTENSIONS 中
      2) 所在目录名命中 UPDATE_FOLDER_NAMES，或文件名含安装包关键词
      3) 文件大小 >= INSTALLER_MIN_SIZE（排除小工具/配置文件）
      4) 不在受保护段下（roots 仅限 AppData/ProgramData，不触及个人目录）

    产出 rule["_update_sources"]：按目录分组的安装包信息，结构同 deep 的 folder_summaries，
    但 packages 字段记录每个安装包的 文件名 / 版本 / 大小 / 路径。
    """
    count = 0
    size = 0
    files = []
    # {目录路径: {app, count, size, packages: [{name, version, size, path, ext}]}}
    sources = {}
    capped = False
    for root in rule["roots"]:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            # 更新安装包扫描的剪枝（比 deep 宽松，允许 download/installer 等）
            dirnames[:] = [d for d in dirnames if d.lower() not in UPDATE_SKIP_SEGMENTS]
            segs = [s.lower() for s in dirpath.split(os.sep)]
            in_update_dir = any(seg in UPDATE_FOLDER_NAMES for seg in segs)
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in INSTALLER_EXTENSIONS:
                    continue
                # 目录名不命中时，靠文件名关键词补充召回
                if not in_update_dir and not _looks_like_installer(fn):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                # 排除过小文件
                if sz < INSTALLER_MIN_SIZE:
                    continue
                count += 1
                size += sz
                summary = sources.setdefault(
                    dirpath,
                    {"app": app_name_for_folder(dirpath, root),
                     "count": 0, "size": 0, "packages": []},
                )
                summary["count"] += 1
                summary["size"] += sz
                summary["packages"].append({
                    "name": fn,
                    "version": _parse_version(fn),
                    "size": sz,
                    "path": fp,
                    "ext": ext,
                })
                if not capped:
                    files.append((fp, sz))
                    if len(files) >= DEEP_CAP:
                        capped = True
    rule["_update_sources"] = sources
    return count, size, files


def scan_rule(rule):
    t = rule.get("type")
    if t == "deep":
        return scan_deep_rule(rule)
    if t == "update":
        return scan_update_packages_rule(rule)
    return scan_path_rule(rule)


def clean_files(files):
    freed = 0
    deleted = 0
    skipped = 0
    for fp, sz in files:
        try:
            if os.path.isfile(fp) or os.path.islink(fp):
                os.remove(fp)
                freed += sz
                deleted += 1
            else:
                skipped += 1
        except (OSError, PermissionError):
            skipped += 1
    return freed, deleted, skipped


# ---------- 资源管理器打开（v2.3.2 新增） ----------
def open_in_explorer(path):
    """
    在 Windows 文件资源管理器中打开并定位到指定路径。
      - 路径是目录：直接打开该目录
      - 路径是文件：用 explorer /select, 定位并选中该文件
    路径不存在时弹窗提示，不抛异常。
    """
    if not path:
        mb.showwarning("提示", "该清理项没有对应的文件路径。")
        return
    # 规范化路径分隔（explorer 对正斜杠支持不佳）
    p = os.path.normpath(path)
    try:
        if os.path.isdir(p):
            # 直接打开目录
            subprocess.Popen(["explorer", p])
        elif os.path.isfile(p):
            # 定位到文件（/select, 与路径之间无空格）
            subprocess.Popen(["explorer", "/select,", p])
        else:
            # 路径不存在：尝试打开其父目录
            parent = os.path.dirname(p)
            if parent and os.path.isdir(parent):
                subprocess.Popen(["explorer", parent])
            else:
                mb.showwarning("提示", f"路径不存在或已被清理：\n{p}")
    except Exception as e:
        mb.showerror("打开失败", f"无法在资源管理器中打开：\n{p}\n\n{e}")


# ---------- 按二级选择过滤清理文件（v2.3.2 新增） ----------
def filter_files_by_selection(rule, files):
    """
    根据 rule 上的二级选择状态过滤待清理文件列表。

    - deep 规则：若存在 _selected_folders（dirpath 集合），仅保留属于选中文件夹的文件；
      否则（None）清理全部（与一级勾选一致）。
    - update 规则：若存在 _selected_packages（filepath 集合），仅保留选中文件；
      否则清理全部。
    - path 规则：无二级选择，直接返回全部。
    """
    t = rule.get("type")
    if t == "deep":
        sel = rule.get("_selected_folders")
        if sel is None:
            return files
        sel_set = set(sel)
        return [(fp, sz) for fp, sz in files
                if os.path.dirname(fp) in sel_set]
    if t == "update":
        sel = rule.get("_selected_packages")
        if sel is None:
            return files
        sel_set = set(sel)
        return [(fp, sz) for fp, sz in files if fp in sel_set]
    return files


# ============================================================
#  动画粒子背景层（v2.3.0 新增）
#  - Canvas 实现的垂直渐变 + 漂浮发光粒子
#  - 粒子用预创建 oval + coords 原地更新，避免每帧 delete/recreate 开销
#  - 支持 burst() 在指定位置迸射短生命粒子（交互反馈）
# ============================================================
class AnimatedBackground:
    GRAD_BANDS = 48          # 渐变条带数（一次绘制，resize 时重绘）
    DEFAULT_PARTICLES = 46   # 主窗口粒子数
    DIALOG_PARTICLES = 22   # 对话框粒子数
    FRAME_MS = 33            # ~30fps

    def __init__(self, parent, particle_count=None, width=1120, height=800):
        self.parent = parent
        self.w = width
        self.h = height
        self.particle_count = particle_count or self.DEFAULT_PARTICLES
        self.canvas = tk.Canvas(parent, highlightthickness=0, bd=0,
                                bg=C_BG, width=width, height=height)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        # 渐变三段：顶 -> 中 -> 底
        self.grad_stops = [
            (0.0, _hex_rgb(C_BG_TOP)),
            (0.5, _hex_rgb(C_BG_MID)),
            (1.0, _hex_rgb(C_BG_BOT)),
        ]
        self.particles = []
        self.particle_items = []   # core oval id 列表
        self.particle_glows = []    # glow oval id 列表
        self.bursts = []            # 交互反馈粒子（动态创建/销毁）
        self._grad_dirty = True
        self._running = True
        self._init_particles()
        parent.bind("<Configure>", self._on_resize, add="+")
        self._animate()

    # ---------- 初始化 ----------
    def _init_particles(self):
        for _ in range(self.particle_count):
            p = self._new_particle()
            self.particles.append(p)
            # 光晕（外圈描边，半透明感）
            glow = self.canvas.create_oval(0, 0, 0, 0, outline=p["hue"], width=1)
            core = self.canvas.create_oval(0, 0, 0, 0, fill=p["hue"], outline="")
            self.particle_glows.append(glow)
            self.particle_items.append(core)

    def _new_particle(self, y=None):
        return {
            "x": random.uniform(0, self.w),
            "y": y if y is not None else random.uniform(0, self.h),
            "r": random.uniform(0.9, 2.8),
            "vy": random.uniform(-0.42, -0.10),   # 上浮
            "vx": random.uniform(-0.14, 0.14),
            "base": random.uniform(0.55, 1.0),    # 闪烁基准半径系数
            "phase": random.uniform(0, 6.283),
            "pseed": random.uniform(0.04, 0.075), # 闪烁速度
            "hue": random.choice(PARTICLE_COLORS),
        }

    # ---------- 渐变 ----------
    def _grad_color(self, t):
        stops = self.grad_stops
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0
                return (int(c0[0] + (c1[0] - c0[0]) * f),
                        int(c0[1] + (c1[1] - c0[1]) * f),
                        int(c0[2] + (c1[2] - c0[2]) * f))
        return stops[-1][1]

    def _draw_gradient(self):
        self.canvas.delete("grad")
        bands = self.GRAD_BANDS
        for i in range(bands):
            t0 = i / bands
            t1 = (i + 1) / bands
            c = self._grad_color((t0 + t1) / 2)
            y0 = t0 * self.h
            y1 = t1 * self.h + 1
            self.canvas.create_rectangle(
                0, y0, self.w, y1,
                fill="#%02x%02x%02x" % c, outline="", tags="grad"
            )
        # 渐变在最底层
        self.canvas.tag_lower("grad")

    # ---------- 粒子爆发（交互反馈） ----------
    def burst(self, x, y, color=None, count=22):
        color = color or C_PRIMARY_GLOW
        for _ in range(count):
            ang = random.uniform(0, 6.283)
            spd = random.uniform(1.6, 5.2)
            self.bursts.append({
                "x": x, "y": y,
                "vx": math.cos(ang) * spd,
                "vy": math.sin(ang) * spd - 1.2,  # 略带上抛
                "r": random.uniform(1.4, 3.4),
                "life": 1.0,
                "decay": random.uniform(0.022, 0.05),
                "color": color,
            })

    # ---------- 调度 ----------
    def _on_resize(self, _e):
        try:
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()
        except Exception:
            return
        if w > 10 and h > 10:
            self.w, self.h = w, h
            self._grad_dirty = True

    def stop(self):
        self._running = False

    def _animate(self):
        if not self._running:
            return
        # 窗口不可见时跳过绘制（节省 CPU）
        try:
            viewable = self.parent.winfo_viewable()
        except Exception:
            viewable = True
        if viewable:
            # 渐变（仅在脏时重绘）
            if self._grad_dirty:
                self._draw_gradient()
                self._grad_dirty = False

            # 更新粒子位置（coords 原地更新）
            for p, glow, core in zip(self.particles, self.particle_glows, self.particle_items):
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["phase"] += p["pseed"]
                # 越界回环
                if p["y"] < -12:
                    p["y"] = self.h + 12
                    p["x"] = random.uniform(0, self.w)
                if p["x"] < -12:
                    p["x"] = self.w + 12
                elif p["x"] > self.w + 12:
                    p["x"] = -12
                # 闪烁（半径脉动，模拟透明度变化）
                twinkle = p["base"] * (0.65 + 0.35 * math.sin(p["phase"]))
                r = max(0.3, p["r"] * twinkle)
                self.canvas.coords(glow, p["x"] - r * 2.6, p["y"] - r * 2.6,
                                   p["x"] + r * 2.6, p["y"] + r * 2.6)
                self.canvas.coords(core, p["x"] - r, p["y"] - r,
                                  p["x"] + r, p["y"] + r)

            # 爆发粒子（动态 create/delete）
            if self.bursts:
                self.canvas.delete("burst")
                alive = []
                for b in self.bursts:
                    b["x"] += b["vx"]
                    b["y"] += b["vy"]
                    b["vy"] += 0.09  # 重力
                    b["life"] -= b["decay"]
                    if b["life"] > 0:
                        r = max(0.5, b["r"] * b["life"])
                        self.canvas.create_oval(
                            b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r,
                            fill=b["color"], outline="", tags="burst"
                        )
                        alive.append(b)
                self.bursts = alive
                # 爆发粒子在前景
                self.canvas.tag_raise("burst")

        self.parent.after(self.FRAME_MS, self._animate)


def _hex_rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------- 毛玻璃卡片工厂 ----------
def make_glass_card(parent, *, fg=None, border=None, radius=14, height=None):
    """创建一个毛玻璃风格的 CTkFrame。"""
    fg = C_GLASS if fg is None else fg
    border = C_GLASS_BORDER if border is None else border
    kw = dict(fg_color=fg, corner_radius=radius,
              border_width=1, border_color=border)
    if height is not None:
        kw["height"] = height
    return ctk.CTkFrame(parent, **kw)


def bind_hover(card, base=None, hover=None):
    """绑定卡片悬停高亮（鼠标在卡片任意子元素上时保持高亮）。"""
    base = C_GLASS if base is None else base
    hover = C_GLASS_HOV if hover is None else hover
    def on_enter(_e):
        card.configure(fg_color=hover)
    def on_leave(e):
        try:
            rx = card.winfo_pointerx() - card.winfo_rootx()
            ry = card.winfo_pointery() - card.winfo_rooty()
            if 0 <= rx <= card.winfo_width() and 0 <= ry <= card.winfo_height():
                return  # 仍在卡片内（进入子元素）
        except Exception:
            pass
        card.configure(fg_color=base)
    card.bind("<Enter>", on_enter)
    card.bind("<Leave>", on_leave)


# ---------- 文件夹归属详情对话框（分页 + 搜索 + 异步渲染 + 毛玻璃风格） ----------
class FolderDetailDialog(ctk.CTkToplevel):
    """
    显示第三方应用深度清理中每个待清理文件夹的归属信息。

    性能优化点：
    1. 分页：每页仅渲染 PAGE_SIZE 条，避免一次性创建数百个 Widget 导致卡顿。
    2. 搜索：按 软件名 / 路径 / 垃圾类型 实时过滤，过滤后重新分页。
    3. 异步渲染：用 after 分批插入当前页的卡片（每批 BATCH 个），主线程不阻塞。
    4. 按大小排序，便于用户优先关注大文件夹。
    5. v2.3.0：毛玻璃风格卡片 + 轻量粒子背景（与主窗口视觉一致）。
    """

    PAGE_SIZE = 50        # 每页条数
    BATCH = 10            # 每批异步渲染的卡片数

    def __init__(self, parent, rule):
        super().__init__(parent)
        self.title("第三方应用深度清理 · 文件夹归属")
        self.geometry("1120x760")
        self.minsize(940, 640)
        self.transient(parent)

        self.configure(fg_color=C_BG)

        self.rule = rule
        self.all_items = []
        self.filtered = []
        self.current_page = 0
        self._render_job = None
        # 二级选择状态：{dirpath: BooleanVar}，默认全选（与一级目录一致）
        self._folder_vars = {}

        # 轻量粒子背景
        self.bg = AnimatedBackground(self, particle_count=AnimatedBackground.DIALOG_PARTICLES)

        # 透明内容层（让背景粒子透出）
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        # 确保内容在粒子背景之上
        self.content.lift()

        self._build_ui()
        self._load_data(rule)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ---- 顶部标题区（毛玻璃面板） ----
        header = make_glass_card(self.content, fg=C_GLASS_2, height=96)
        header.pack(fill="x", padx=16, pady=(16, 8))
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header, text="📁  文件夹归属详情",
            font=fnt(20, "bold"), text_color=C_TEXT, anchor="w"
        )
        title.pack(side="left", padx=24, pady=(18, 0))

        sub = ctk.CTkLabel(
            header,
            text="展示每个待清理文件夹所属的软件及垃圾类型分类，便于确认后再清理",
            font=fnt(12), text_color=C_TEXT_DIM, anchor="w"
        )
        sub.pack(side="left", padx=20, pady=(26, 0))

        self.stat_label = ctk.CTkLabel(
            header, text="", font=fnt(13, "bold"), text_color=C_SUCCESS, anchor="e"
        )
        self.stat_label.pack(side="right", padx=24, pady=(26, 0))

        # ---- 搜索栏 ----
        search_bar = ctk.CTkFrame(self.content, fg_color="transparent", height=44)
        search_bar.pack(fill="x", padx=16, pady=(4, 8))
        search_bar.pack_propagate(False)

        ctk.CTkLabel(search_bar, text="🔍", font=fnt(14), text_color=C_TEXT_DIM).pack(
            side="left", padx=(8, 4)
        )
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = ctk.CTkEntry(
            search_bar, textvariable=self.search_var,
            placeholder_text="按软件名 / 路径 / 垃圾类型筛选（如 Chrome、cache、日志）",
            font=fnt(12), height=36, fg_color=C_GLASS, border_color=C_GLASS_BORDER,
            text_color=C_TEXT, corner_radius=10
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.clear_btn = ctk.CTkButton(
            search_bar, text="清除", width=64, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM, hover_color=C_GLASS_HOV,
            corner_radius=10,
            command=lambda: self.search_var.set("")
        )
        self.clear_btn.pack(side="left")

        # 全选 / 反选（对当前过滤结果生效）
        self.select_all_btn = ctk.CTkButton(
            search_bar, text="全选", width=64, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_PRIMARY, text_color=C_PRIMARY, hover_color=C_GLASS_HOV,
            corner_radius=10, command=lambda: self._set_all_filtered(True)
        )
        self.select_all_btn.pack(side="left", padx=(8, 0))

        self.invert_btn = ctk.CTkButton(
            search_bar, text="反选", width=64, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=10, command=self._invert_filtered
        )
        self.invert_btn.pack(side="left", padx=(8, 0))

        # 已选统计
        self.sel_label = ctk.CTkLabel(
            search_bar, text="", font=fnt(12), text_color=C_SUCCESS
        )
        self.sel_label.pack(side="left", padx=(12, 0))

        # ---- 列表区 ----
        self.list_frame = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=C_GLASS_BORDER, scrollbar_button_hover_color=C_TEXT_FAINT
        )
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        # ---- 底部分页栏（毛玻璃面板） ----
        footer = make_glass_card(self.content, fg=C_GLASS_2, height=58)
        footer.pack(fill="x", padx=16, pady=(0, 16))
        footer.pack_propagate(False)

        self.prev_btn = ctk.CTkButton(
            footer, text="◀ 上一页", width=110, height=34,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=8, command=self._prev_page
        )
        self.prev_btn.pack(side="left", padx=(16, 6), pady=12)

        self.next_btn = ctk.CTkButton(
            footer, text="下一页 ▶", width=110, height=34,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=8, command=self._next_page
        )
        self.next_btn.pack(side="left", padx=6, pady=12)

        self.page_label = ctk.CTkLabel(
            footer, text="", font=fnt(12), text_color=C_TEXT_DIM
        )
        self.page_label.pack(side="left", padx=16, pady=12)

        self.close_btn = ctk.CTkButton(
            footer, text="关闭", width=90, height=34,
            font=fnt(12, "bold"), fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV,
            corner_radius=8, command=self._on_close
        )
        self.close_btn.pack(side="right", padx=(6, 16), pady=12)

        self.total_size_label = ctk.CTkLabel(
            footer, text="", font=fnt(12), text_color=C_TEXT_DIM
        )
        self.total_size_label.pack(side="right", padx=16, pady=12)

    def _load_data(self, rule):
        folders = rule.get("_deep_folders", {})
        self.all_items = sorted(folders.items(), key=lambda p: p[1]["size"], reverse=True)
        total_count = len(self.all_items)
        total_size = sum(it["size"] for _, it in self.all_items)
        # 初始化每个文件夹的选择变量（默认全选，与一级目录一致）
        # 若 rule 已有 _selected_folders（用户曾操作过），则恢复其状态
        prev_sel = rule.get("_selected_folders")
        for path, _ in self.all_items:
            default = "on" if (prev_sel is None or path in prev_sel) else "off"
            self._folder_vars[path] = ctk.BooleanVar(value=(default == "on"))
        if total_count == 0:
            self.stat_label.configure(text="无数据", text_color=C_TEXT_DIM)
            self._show_empty()
            return
        self.stat_label.configure(
            text=f"共 {total_count} 个文件夹 · 合计 {fmt_size(total_size)}",
            text_color=C_SUCCESS
        )
        self._apply_filter()

    def _apply_filter(self):
        kw = self.search_var.get().strip().lower()
        if not kw:
            self.filtered = self.all_items
        else:
            self.filtered = [
                (p, it) for p, it in self.all_items
                if kw in p.lower()
                or kw in it["app"].lower()
                or any(kw in t.lower() for t in it.get("types", set()))
            ]
        self.current_page = 0
        self._render_page()

    def _show_empty(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.page_label.configure(text="无数据")
        self.prev_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        ctk.CTkLabel(
            self.list_frame,
            text="本次扫描没有发现可清理的第三方应用文件夹。",
            font=fnt(13), text_color=C_TEXT_DIM
        ).pack(pady=60)

    def _render_page(self):
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        for w in self.list_frame.winfo_children():
            w.destroy()

        total = len(self.filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page >= total_pages:
            self.current_page = total_pages - 1
        if self.current_page < 0:
            self.current_page = 0

        start = self.current_page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, total)

        self.page_label.configure(
            text=f"第 {self.current_page + 1} / {total_pages} 页  ·  当前显示 {start + 1}-{end} / {total}"
        )
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

        page_total_size = sum(it["size"] for _, it in self.filtered[start:end])
        self.total_size_label.configure(
            text=f"本页合计 {fmt_size(page_total_size)}"
        )

        if total == 0:
            ctk.CTkLabel(
                self.list_frame,
                text="没有匹配的文件夹，试试更换关键字或清除筛选。",
                font=fnt(13), text_color=C_TEXT_DIM
            ).pack(pady=60)
            return

        page_items = self.filtered[start:end]
        self._render_batch(page_items, 0)
        self._update_sel_label()

    def _render_batch(self, items, index):
        if index >= len(items):
            self._render_job = None
            return
        end = min(index + self.BATCH, len(items))
        for i in range(index, end):
            self._render_item(*items[i])
        self._render_job = self.after(10, lambda: self._render_batch(items, end))

    def _render_item(self, path, item):
        card = make_glass_card(self.list_frame, radius=10)
        card.pack(fill="x", padx=4, pady=4)
        bind_hover(card, C_GLASS, C_GLASS_HOV)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))

        # 选择复选框（默认选中，与一级目录一致）
        var = self._folder_vars.get(path)
        if var is None:
            var = ctk.BooleanVar(value=True)
            self._folder_vars[path] = var
        cb = ctk.CTkCheckBox(
            top, text="", variable=var, onvalue=True, offvalue=False,
            width=24, checkbox_width=18, checkbox_height=18,
            fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV, corner_radius=4,
            command=self._update_sel_label
        )
        cb.pack(side="left", padx=(0, 8))

        app_label = ctk.CTkLabel(
            top, text=f"🖥  {item['app']}",
            font=fnt(14, "bold"), text_color=C_TEXT, anchor="w"
        )
        app_label.pack(side="left", padx=(0, 10))

        types = sorted(item.get("types", set()))
        for t in types:
            color = TYPE_COLORS.get(t, C_TEXT_FAINT)
            badge = ctk.CTkLabel(
                top, text=t,
                font=fnt(10, "bold"), text_color="#ffffff",
                fg_color=color, corner_radius=10,
                padx=8, pady=0, height=20
            )
            badge.pack(side="left", padx=(0, 6))

        # 「📂 打开」按钮：定位到该文件夹
        open_btn = ctk.CTkButton(
            top, text="📂", width=28, height=22,
            font=fnt(11), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM,
            hover_color=C_GLASS_HOV, corner_radius=5,
            command=lambda p=path: open_in_explorer(p)
        )
        open_btn.pack(side="right", padx=(4, 0))

        size_label = ctk.CTkLabel(
            top, text=fmt_size(item["size"]),
            font=fnt(14, "bold"), text_color=C_SUCCESS, anchor="e"
        )
        size_label.pack(side="right", padx=(8, 0))

        count_label = ctk.CTkLabel(
            top, text=f"{item['count']:,} 个文件",
            font=fnt(11), text_color=C_TEXT_DIM, anchor="e"
        )
        count_label.pack(side="right", padx=12)

        path_label = ctk.CTkLabel(
            card, text=path,
            font=mono_fnt(11), text_color=C_TEXT_DIM, anchor="w",
            wraplength=1000
        )
        path_label.pack(fill="x", padx=14, pady=(0, 10))

    def _set_all_filtered(self, checked):
        """对当前过滤结果全选/全不选。"""
        for path, _ in self.filtered:
            var = self._folder_vars.get(path)
            if var is not None:
                var.set(checked)
        self._update_sel_label()

    def _invert_filtered(self):
        """对当前过滤结果反选。"""
        for path, _ in self.filtered:
            var = self._folder_vars.get(path)
            if var is not None:
                var.set(not var.get())
        self._update_sel_label()

    def _update_sel_label(self):
        """更新已选统计（按全部项目，而非仅当前页）。"""
        sel_count = sum(1 for v in self._folder_vars.values() if v.get())
        total = len(self._folder_vars)
        sel_size = sum(it["size"] for p, it in self.all_items
                       if self._folder_vars.get(p) and self._folder_vars[p].get())
        if total == 0:
            self.sel_label.configure(text="", text_color=C_TEXT_DIM)
            return
        self.sel_label.configure(
            text=f"已选 {sel_count}/{total} · {fmt_size(sel_size)}",
            text_color=C_SUCCESS if sel_count else C_TEXT_DIM
        )

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next_page(self):
        total = len(self.filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_page()

    def _on_close(self):
        # 保存二级选择到 rule（供清理逻辑使用）
        sel = {p for p, v in self._folder_vars.items() if v.get()}
        # 仅当有数据时记录选择（空集合表示取消全部，仍需记录）
        if self.all_items:
            self.rule["_selected_folders"] = sel
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None
        try:
            self.bg.stop()
        except Exception:
            pass
        self.destroy()


# ---------- 软件更新安装包详情对话框（可展开/收起，与第三方应用详情风格统一） ----------
class PackageDetailDialog(ctk.CTkToplevel):
    """
    展示软件更新安装包扫描结果。

    数据来源：rule["_update_sources"]（按目录分组的安装包信息）。
    交互方式与 FolderDetailDialog 保持一致（毛玻璃 + 分页 + 搜索 + 异步渲染 + 轻量粒子背景），
    但每个条目是「软件来源」可折叠卡片：点击标题行展开/收起该来源下的安装包列表，
    列表中每个安装包显示 文件名 / 版本徽章 / 大小 / 路径。
    """

    PAGE_SIZE = 50
    BATCH = 6

    def __init__(self, parent, rule):
        super().__init__(parent)
        self.title("软件更新安装包 · 详情")
        self.geometry("1120x760")
        self.minsize(940, 640)
        self.transient(parent)

        self.configure(fg_color=C_BG)

        self.all_items = []      # [(dirpath, summary), ...] 按大小降序
        self.filtered = []
        self.current_page = 0
        self._render_job = None
        self._expanded = set()   # 当前展开的 dirpath 集合
        self.rule = rule
        # 二级选择状态：{安装包 filepath: BooleanVar}，默认全选
        self._pkg_vars = {}

        # 轻量粒子背景
        self.bg = AnimatedBackground(self, particle_count=AnimatedBackground.DIALOG_PARTICLES)

        # 透明内容层
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.content.lift()

        self._build_ui()
        self._load_data(rule)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ---- 顶部标题区（毛玻璃面板） ----
        header = make_glass_card(self.content, fg=C_GLASS_2, height=96)
        header.pack(fill="x", padx=16, pady=(16, 8))
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header, text="📦  软件更新安装包",
            font=fnt(20, "bold"), text_color=C_TEXT, anchor="w"
        )
        title.pack(side="left", padx=24, pady=(18, 0))

        sub = ctk.CTkLabel(
            header,
            text="按软件来源分组，点击展开查看每个安装包的文件名 / 版本 / 大小",
            font=fnt(12), text_color=C_TEXT_DIM, anchor="w"
        )
        sub.pack(side="left", padx=20, pady=(26, 0))

        self.stat_label = ctk.CTkLabel(
            header, text="", font=fnt(13, "bold"), text_color=C_SUCCESS, anchor="e"
        )
        self.stat_label.pack(side="right", padx=24, pady=(26, 0))

        # ---- 搜索栏 ----
        search_bar = ctk.CTkFrame(self.content, fg_color="transparent", height=44)
        search_bar.pack(fill="x", padx=16, pady=(4, 8))
        search_bar.pack_propagate(False)

        ctk.CTkLabel(search_bar, text="🔍", font=fnt(14), text_color=C_TEXT_DIM).pack(
            side="left", padx=(8, 4)
        )
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = ctk.CTkEntry(
            search_bar, textvariable=self.search_var,
            placeholder_text="按软件名 / 文件名 / 版本筛选（如 Chrome、setup、1.2.3）",
            font=fnt(12), height=36, fg_color=C_GLASS, border_color=C_GLASS_BORDER,
            text_color=C_TEXT, corner_radius=10
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.clear_btn = ctk.CTkButton(
            search_bar, text="清除", width=64, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM, hover_color=C_GLASS_HOV,
            corner_radius=10,
            command=lambda: self.search_var.set("")
        )
        self.clear_btn.pack(side="left")

        self.expand_all_btn = ctk.CTkButton(
            search_bar, text="全部展开", width=90, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_PRIMARY, text_color=C_PRIMARY, hover_color=C_GLASS_HOV,
            corner_radius=10, command=self._expand_all
        )
        self.expand_all_btn.pack(side="left", padx=(8, 0))

        self.collapse_all_btn = ctk.CTkButton(
            search_bar, text="全部收起", width=90, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM, hover_color=C_GLASS_HOV,
            corner_radius=10, command=self._collapse_all
        )
        self.collapse_all_btn.pack(side="left", padx=(8, 0))

        # 全选 / 反选（对当前过滤结果生效）
        self.select_all_btn = ctk.CTkButton(
            search_bar, text="全选", width=64, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_PRIMARY, text_color=C_PRIMARY, hover_color=C_GLASS_HOV,
            corner_radius=10, command=lambda: self._set_all_filtered(True)
        )
        self.select_all_btn.pack(side="left", padx=(8, 0))

        self.invert_btn = ctk.CTkButton(
            search_bar, text="反选", width=64, height=36,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=10, command=self._invert_filtered
        )
        self.invert_btn.pack(side="left", padx=(8, 0))

        # 已选统计
        self.sel_label = ctk.CTkLabel(
            search_bar, text="", font=fnt(12), text_color=C_SUCCESS
        )
        self.sel_label.pack(side="left", padx=(12, 0))

        # ---- 列表区 ----
        self.list_frame = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=C_GLASS_BORDER, scrollbar_button_hover_color=C_TEXT_FAINT
        )
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        # ---- 底部分页栏（毛玻璃面板） ----
        footer = make_glass_card(self.content, fg=C_GLASS_2, height=58)
        footer.pack(fill="x", padx=16, pady=(0, 16))
        footer.pack_propagate(False)

        self.prev_btn = ctk.CTkButton(
            footer, text="◀ 上一页", width=110, height=34,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=8, command=self._prev_page
        )
        self.prev_btn.pack(side="left", padx=(16, 6), pady=12)

        self.next_btn = ctk.CTkButton(
            footer, text="下一页 ▶", width=110, height=34,
            font=fnt(12), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=8, command=self._next_page
        )
        self.next_btn.pack(side="left", padx=6, pady=12)

        self.page_label = ctk.CTkLabel(
            footer, text="", font=fnt(12), text_color=C_TEXT_DIM
        )
        self.page_label.pack(side="left", padx=16, pady=12)

        self.close_btn = ctk.CTkButton(
            footer, text="关闭", width=90, height=34,
            font=fnt(12, "bold"), fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV,
            corner_radius=8, command=self._on_close
        )
        self.close_btn.pack(side="right", padx=(6, 16), pady=12)

        self.total_size_label = ctk.CTkLabel(
            footer, text="", font=fnt(12), text_color=C_TEXT_DIM
        )
        self.total_size_label.pack(side="right", padx=16, pady=12)

    def _load_data(self, rule):
        sources = rule.get("_update_sources", {})
        self.all_items = sorted(sources.items(), key=lambda p: p[1]["size"], reverse=True)
        total_count = len(self.all_items)
        total_size = sum(it["size"] for _, it in self.all_items)
        total_pkgs = sum(it["count"] for _, it in self.all_items)
        # 初始化每个安装包的选择变量（默认全选）；若 rule 已有 _selected_packages 则恢复
        prev_sel = rule.get("_selected_packages")
        for _, it in self.all_items:
            for pkg in it.get("packages", []):
                default = (prev_sel is None) or (pkg["path"] in prev_sel)
                self._pkg_vars[pkg["path"]] = ctk.BooleanVar(value=default)
        if total_count == 0:
            self.stat_label.configure(text="无数据", text_color=C_TEXT_DIM)
            self._show_empty()
            return
        self.stat_label.configure(
            text=f"{total_count} 个来源 · {total_pkgs} 个安装包 · {fmt_size(total_size)}",
            text_color=C_SUCCESS
        )
        self._apply_filter()

    def _apply_filter(self):
        kw = self.search_var.get().strip().lower()
        if not kw:
            self.filtered = self.all_items
        else:
            self.filtered = []
            for path, it in self.all_items:
                if (kw in path.lower()
                        or kw in it["app"].lower()
                        or any(kw in p["name"].lower() or kw in p["version"].lower()
                               for p in it.get("packages", []))):
                    self.filtered.append((path, it))
        self.current_page = 0
        self._render_page()

    def _show_empty(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.page_label.configure(text="无数据")
        self.prev_btn.configure(state="disabled")
        self.next_btn.configure(state="disabled")
        ctk.CTkLabel(
            self.list_frame,
            text="本次扫描没有发现软件更新安装包。",
            font=fnt(13), text_color=C_TEXT_DIM
        ).pack(pady=60)

    def _render_page(self):
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        for w in self.list_frame.winfo_children():
            w.destroy()

        total = len(self.filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page >= total_pages:
            self.current_page = total_pages - 1
        if self.current_page < 0:
            self.current_page = 0

        start = self.current_page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, total)

        self.page_label.configure(
            text=f"第 {self.current_page + 1} / {total_pages} 页  ·  当前显示 {start + 1}-{end} / {total}"
        )
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

        page_total_size = sum(it["size"] for _, it in self.filtered[start:end])
        self.total_size_label.configure(text=f"本页合计 {fmt_size(page_total_size)}")

        if total == 0:
            ctk.CTkLabel(
                self.list_frame,
                text="没有匹配的安装包，试试更换关键字或清除筛选。",
                font=fnt(13), text_color=C_TEXT_DIM
            ).pack(pady=60)
            return

        page_items = self.filtered[start:end]
        self._render_batch(page_items, 0)
        self._update_sel_label()

    def _render_batch(self, items, index):
        if index >= len(items):
            self._render_job = None
            return
        end = min(index + self.BATCH, len(items))
        for i in range(index, end):
            self._render_item(*items[i])
        self._render_job = self.after(10, lambda: self._render_batch(items, end))

    def _render_item(self, path, item):
        """渲染一个软件来源卡片（可展开/收起，来源级与安装包级均可勾选）。"""
        card = make_glass_card(self.list_frame, radius=10)
        card.pack(fill="x", padx=4, pady=4)
        bind_hover(card, C_GLASS, C_GLASS_HOV)

        # 标题行（点击切换展开）
        header_row = ctk.CTkFrame(card, fg_color="transparent", cursor="hand2")
        header_row.pack(fill="x", padx=14, pady=(10, 4))

        # 来源级全选 checkbox（选中/取消该来源下所有安装包）
        src_var = ctk.BooleanVar(value=self._is_source_all_selected(item))
        src_cb = ctk.CTkCheckBox(
            header_row, text="", variable=src_var, onvalue=True, offvalue=False,
            width=24, checkbox_width=18, checkbox_height=18,
            fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV, corner_radius=4,
            command=lambda it=item, v=src_var: self._toggle_source(it, v)
        )
        src_cb.pack(side="left", padx=(0, 8))

        toggle = ctk.CTkLabel(
            header_row, text="▶", font=fnt(12, "bold"), text_color=C_PRIMARY,
            width=16
        )
        toggle.pack(side="left", padx=(0, 8))

        app_label = ctk.CTkLabel(
            header_row, text=f"🖥  {item['app']}",
            font=fnt(14, "bold"), text_color=C_TEXT, anchor="w"
        )
        app_label.pack(side="left", padx=(0, 10))

        cnt_label = ctk.CTkLabel(
            header_row, text=f"{item['count']} 个安装包",
            font=fnt(11), text_color=C_TEXT_DIM, anchor="w"
        )
        cnt_label.pack(side="left", padx=(0, 10))

        # 来源级「📂 打开」按钮：定位到来源目录
        open_src_btn = ctk.CTkButton(
            header_row, text="📂", width=28, height=22,
            font=fnt(11), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM,
            hover_color=C_GLASS_HOV, corner_radius=5,
            command=lambda p=path: open_in_explorer(p)
        )
        open_src_btn.pack(side="right", padx=(4, 0))

        size_label = ctk.CTkLabel(
            header_row, text=fmt_size(item["size"]),
            font=fnt(14, "bold"), text_color=C_SUCCESS, anchor="e"
        )
        size_label.pack(side="right")

        # 安装包列表容器（初始收起）
        body = ctk.CTkFrame(card, fg_color="transparent")
        # 不 pack，初始隐藏

        # 目录路径（小字，放标题下方）
        path_label = ctk.CTkLabel(
            card, text=path,
            font=mono_fnt(10), text_color=C_TEXT_FAINT, anchor="w",
            wraplength=1000
        )
        path_label.pack(fill="x", padx=14, pady=(0, 8))

        # 填充安装包列表
        for pkg in sorted(item.get("packages", []), key=lambda p: p["size"], reverse=True):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=3)

            # 安装包级 checkbox
            pvar = self._pkg_vars.get(pkg["path"])
            if pvar is None:
                pvar = ctk.BooleanVar(value=True)
                self._pkg_vars[pkg["path"]] = pvar
            pcb = ctk.CTkCheckBox(
                row, text="", variable=pvar, onvalue=True, offvalue=False,
                width=24, checkbox_width=16, checkbox_height=16,
                fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV, corner_radius=3,
                command=lambda it=item, v=src_var: self._sync_source_var(it, v)
            )
            pcb.pack(side="left", padx=(0, 6))

            name_label = ctk.CTkLabel(
                row, text=f"📄  {pkg['name']}",
                font=fnt(12), text_color=C_TEXT, anchor="w"
            )
            name_label.pack(side="left", padx=(0, 8))

            # 版本徽章
            ver_color = C_PRIMARY if pkg["version"] != "—" else C_TEXT_FAINT
            ver_badge = ctk.CTkLabel(
                row, text=f"v {pkg['version']}",
                font=fnt(10, "bold"), text_color="#ffffff",
                fg_color=ver_color, corner_radius=8,
                padx=8, pady=0, height=18
            )
            ver_badge.pack(side="left", padx=(0, 8))

            # 扩展名徽章
            ext_badge = ctk.CTkLabel(
                row, text=pkg["ext"].lstrip(".").upper(),
                font=fnt(9, "bold"), text_color=C_TEXT_DIM,
                fg_color=C_GLASS_BORDER, corner_radius=6,
                padx=6, pady=0, height=16
            )
            ext_badge.pack(side="left", padx=(0, 8))

            # 安装包级「📂 打开」按钮：定位到该文件
            open_pkg_btn = ctk.CTkButton(
                row, text="📂", width=26, height=20,
                font=fnt(10), fg_color="transparent", border_width=1,
                border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM,
                hover_color=C_GLASS_HOV, corner_radius=4,
                command=lambda p=pkg["path"]: open_in_explorer(p)
            )
            open_pkg_btn.pack(side="right", padx=(4, 0))

            pkg_size = ctk.CTkLabel(
                row, text=fmt_size(pkg["size"]),
                font=fnt(12, "bold"), text_color=C_WARN, anchor="e"
            )
            pkg_size.pack(side="right")

        def toggle_expand(_e=None):
            if path in self._expanded:
                self._expanded.discard(path)
                body.pack_forget()
                toggle.configure(text="▶")
            else:
                self._expanded.add(path)
                body.pack(fill="x", padx=14, pady=(0, 10), after=path_label)
                toggle.configure(text="▼")

        # 标题行整体可点击（避开 checkbox 与打开按钮，避免误触）
        header_row.bind("<Button-1>", toggle_expand)
        for w in (toggle, app_label, cnt_label, size_label):
            w.bind("<Button-1>", toggle_expand)

        # 应用初始展开状态（支持「全部展开」后重渲染仍保持展开）
        if path in self._expanded:
            body.pack(fill="x", padx=14, pady=(0, 10), after=path_label)
            toggle.configure(text="▼")

    # ---------- 来源级 / 安装包级选择联动 ----------
    def _is_source_all_selected(self, item):
        """该来源下所有安装包是否均已选。"""
        pkgs = item.get("packages", [])
        if not pkgs:
            return False
        return all(self._pkg_vars.get(p["path"]) and self._pkg_vars[p["path"]].get()
                   for p in pkgs)

    def _toggle_source(self, item, src_var):
        """来源级 checkbox：全选/取消该来源下所有安装包。"""
        val = src_var.get()
        for p in item.get("packages", []):
            v = self._pkg_vars.get(p["path"])
            if v is not None:
                v.set(val)
        self._update_sel_label()

    def _sync_source_var(self, item, src_var):
        """安装包级 checkbox 变化时，同步来源级 checkbox 状态。"""
        src_var.set(self._is_source_all_selected(item))
        self._update_sel_label()

    def _set_all_filtered(self, checked):
        """对当前过滤结果中的所有安装包全选/全不选。"""
        for _, it in self.filtered:
            for p in it.get("packages", []):
                v = self._pkg_vars.get(p["path"])
                if v is not None:
                    v.set(checked)
        self._render_page()

    def _invert_filtered(self):
        """对当前过滤结果中的所有安装包反选。"""
        for _, it in self.filtered:
            for p in it.get("packages", []):
                v = self._pkg_vars.get(p["path"])
                if v is not None:
                    v.set(not v.get())
        self._render_page()

    def _update_sel_label(self):
        sel_count = sum(1 for v in self._pkg_vars.values() if v.get())
        total = len(self._pkg_vars)
        sel_size = 0
        for _, it in self.all_items:
            for p in it.get("packages", []):
                v = self._pkg_vars.get(p["path"])
                if v and v.get():
                    sel_size += p["size"]
        if total == 0:
            self.sel_label.configure(text="", text_color=C_TEXT_DIM)
            return
        self.sel_label.configure(
            text=f"已选 {sel_count}/{total} · {fmt_size(sel_size)}",
            text_color=C_SUCCESS if sel_count else C_TEXT_DIM
        )

    def _expand_all(self):
        # 展开当前页可见的所有卡片
        start = self.current_page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, len(self.filtered))
        for path, _ in self.filtered[start:end]:
            self._expanded.add(path)
        self._render_page()

    def _collapse_all(self):
        self._expanded.clear()
        self._render_page()

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next_page(self):
        total = len(self.filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_page()

    def _on_close(self):
        # 保存二级选择到 rule（供清理逻辑使用）
        sel = {p for p, v in self._pkg_vars.items() if v.get()}
        if self._pkg_vars:
            self.rule["_selected_packages"] = sel
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None
        try:
            self.bg.stop()
        except Exception:
            pass
        self.destroy()


# ---------- GUI ----------
class CleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  —  {AUTHOR}  {VERSION}")
        self.geometry("1180x820")
        self.minsize(1000, 720)
        self.theme_name = "dark"
        apply_theme(self.theme_name)
        ctk.set_appearance_mode(self.theme_name)
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=C_BG)

        self.rules = build_rules()
        self.row_widgets = []
        self.scanning = False
        self.cleaning = False
        self.has_scanned = False
        # 响应式网格：根据列表区宽度自动决定每行卡片数（1-4 列）
        self._cols = 2
        self._max_cols_cfg = 2

        self._build_shell()

    def _build_shell(self):
        """按当前主题构建主界面；主题切换时复用。"""
        self.configure(fg_color=C_BG)
        self.bg = AnimatedBackground(self)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.content.lift()

        self._build_header()
        self._build_toolbar()
        self._build_list_area()
        self._build_status_bar()

    def _toggle_theme(self):
        """在明暗主题之间切换，并保留已扫描的项目与勾选状态。"""
        if self.scanning or self.cleaning:
            return
        selected = {item["rule"]["key"] for item in self.row_widgets
                    if item["variable"].get() == "on"}
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        apply_theme(self.theme_name)
        ctk.set_appearance_mode(self.theme_name)
        self.bg.stop()
        self.bg.canvas.destroy()
        self.content.destroy()
        self.row_widgets = []
        self._cols = 2
        self._max_cols_cfg = 2
        self._build_shell()
        if self.has_scanned:
            for child in self.list_container.winfo_children():
                child.destroy()
            for rule in self.rules:
                if "_files" in rule:
                    self._add_row(rule, selected=rule["key"] in selected)
            total_count = sum(r.get("_count", 0) for r in self.rules)
            total_size = sum(r.get("_size", 0) for r in self.rules)
            self.summary_label.configure(text=f"发现 {total_count:,} 个文件", text_color=C_SUCCESS)
            self.metric_label.configure(text=f"预计可释放 {fmt_size(total_size)}", text_color=C_SUCCESS)
            self.status.configure(text="主题已切换；可继续选择或清理扫描结果。", text_color=C_TEXT_DIM)
            self.progress.set(1)

    # ---------- 头部 ----------
    def _build_header(self):
        hdr = make_glass_card(self.content, fg=C_GLASS_2, height=132)
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=24)

        title = ctk.CTkLabel(
            left, text="🧹  C盘垃圾清理工具",
            font=fnt(26, "bold"), text_color=C_TEXT, anchor="w"
        )
        title.pack(anchor="w", pady=(22, 0))

        sub = ctk.CTkLabel(
            left, text=f"作者: {AUTHOR}    版本: {VERSION}",
            font=fnt(12), text_color=C_TEXT_DIM, anchor="w"
        )
        sub.pack(anchor="w", pady=(2, 0))

        self.btn_theme = ctk.CTkButton(
            hdr, text="☀ 亮色" if self.theme_name == "dark" else "◐ 暗色",
            width=104, height=36, font=fnt(12, "bold"), fg_color="transparent",
            border_width=1, border_color=C_GLASS_BORDER, text_color=C_TEXT,
            hover_color=C_GLASS_HOV, corner_radius=10, command=self._toggle_theme
        )
        self.btn_theme.pack(side="right", padx=(0, 18), pady=32)

        dashboard = ctk.CTkFrame(hdr, fg_color=C_PANEL, corner_radius=12,
                                 border_width=1, border_color=C_GLASS_BORDER)
        dashboard.pack(side="right", padx=20, pady=18)

        self.summary_label = ctk.CTkLabel(
            dashboard, text="等待扫描",
            font=fnt(15, "bold"), text_color=C_TEXT, anchor="e"
        )
        self.summary_label.grid(row=0, column=0, columnspan=2, sticky="e", padx=16, pady=(9, 1))
        self.metric_label = ctk.CTkLabel(
            dashboard, text="可释放空间  —",
            font=fnt(11), text_color=C_TEXT_DIM, anchor="e"
        )
        self.metric_label.grid(row=1, column=0, columnspan=2, sticky="e", padx=16, pady=(0, 9))

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        bar = ctk.CTkFrame(self.content, fg_color="transparent", height=72)
        bar.pack(fill="x", padx=16, pady=(4, 4))
        bar.pack_propagate(False)

        self.btn_scan = ctk.CTkButton(
            bar, text="🔍  开始扫描", width=170, height=46,
            font=fnt(15, "bold"), fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV,
            corner_radius=10, command=self.start_scan
        )
        self.btn_scan.pack(side="left", padx=(0, 10))

        self.btn_clean = ctk.CTkButton(
            bar, text="🗑  清理选中", width=170, height=46,
            font=fnt(15, "bold"), fg_color=C_WARN, hover_color=C_WARN_HOV,
            corner_radius=10, command=self.start_clean
        )
        self.btn_clean.pack(side="left", padx=(0, 10))

        self.btn_all = ctk.CTkButton(
            bar, text="全选", width=90, height=40,
            font=fnt(13), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=10, command=lambda: self._set_all(True)
        )
        self.btn_all.pack(side="left", padx=(0, 8))

        self.btn_none = ctk.CTkButton(
            bar, text="全不选", width=90, height=40,
            font=fnt(13), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=10, command=lambda: self._set_all(False)
        )
        self.btn_none.pack(side="left", padx=(0, 8))

        self.btn_exit = ctk.CTkButton(
            bar, text="退出", width=90, height=40,
            font=fnt(13), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT, hover_color=C_GLASS_HOV,
            corner_radius=10, command=self.quit
        )
        self.btn_exit.pack(side="right", padx=(0, 4))

    # ---------- 列表区 ----------
    def _build_list_area(self):
        self.scroll = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=C_GLASS_BORDER, scrollbar_button_hover_color=C_TEXT_FAINT
        )
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        self.list_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True)
        # 响应式列数：监听容器宽度变化，自动重排卡片
        self.list_container.bind("<Configure>", self._on_list_configure)
        self._configure_columns(self._cols)

        self._show_empty_hint()

    def _on_list_configure(self, event):
        """容器尺寸变化时，根据宽度重新计算列数并重排卡片。"""
        width = max(200, event.width)
        # 目标每列约 330px，窗口宽时一行最多 4 个，窄时自动回退到 1 个
        new_cols = max(1, min(3, width // 390))
        if new_cols != self._cols:
            self._cols = new_cols
            self._configure_columns(new_cols)
            self._relayout_cards()

    def _configure_columns(self, cols):
        """设置前 cols 列等宽；多余列 weight=0 不占空间。"""
        max_cfg = max(self._max_cols_cfg, cols)
        for c in range(max_cfg):
            if c < cols:
                self.list_container.columnconfigure(c, weight=1, uniform="col")
            else:
                self.list_container.columnconfigure(c, weight=0)
        self._max_cols_cfg = max_cfg

    def _relayout_cards(self):
        """按当前列数重新 grid 所有已存在的卡片。"""
        cols = self._cols
        for idx, item in enumerate(self.row_widgets):
            card = item["card"]
            try:
                card.grid_forget()
            except Exception:
                pass
            card.grid(row=idx // cols, column=idx % cols,
                      sticky="ew", padx=6, pady=5)

    def _show_empty_hint(self):
        for w in self.list_container.winfo_children():
            w.destroy()
        empty = make_glass_card(self.list_container, radius=14)
        # columnspan 取一个较大值，保证无论响应式几列都横跨整行
        empty.grid(row=0, column=0, columnspan=10, sticky="nsew", padx=8, pady=40)

        ctk.CTkLabel(
            empty, text="👋  欢迎使用 C盘垃圾清理工具",
            font=fnt(20, "bold"), text_color=C_TEXT
        ).pack(pady=(32, 8))

        ctk.CTkLabel(
            empty,
            text=("点击左上角「扫描垃圾」开始分析 C 盘可清理项（含大量第三方应用缓存 / 日志 / 临时文件）。\n\n"
                  "本工具仅清理系统目录与 AppData / ProgramData 中的缓存 / 临时 / 日志，\n"
                  "不会删除你的个人文档 / 桌面 / 下载 / 图片 / 视频。\n\n"
                  "扫描完成后请勾选要清理的项目，再点「清理选中」。"),
            font=fnt(13), text_color=C_TEXT_DIM, justify="center"
        ).pack(pady=(0, 32))

    # ---------- 状态栏 ----------
    def _build_status_bar(self):
        sb = ctk.CTkFrame(self.content, fg_color="transparent", height=64)
        sb.pack(fill="x", padx=16, pady=(0, 16))

        self.progress = ctk.CTkProgressBar(
            sb, height=12, corner_radius=6,
            progress_color=C_PRIMARY, fg_color=C_GLASS_BORDER
        )
        self.progress.pack(fill="x")
        self.progress.set(0)

        self.status = ctk.CTkLabel(
            sb, text="就绪", font=fnt(12), text_color=C_TEXT_DIM, anchor="w"
        )
        self.status.pack(anchor="w", pady=(6, 0))

    # ---------- 交互反馈：从按钮位置迸射粒子 ----------
    def _burst_from_widget(self, widget, color=None, count=22):
        try:
            self.update_idletasks()
            x = widget.winfo_rootx() - self.winfo_rootx() + widget.winfo_width() / 2
            y = widget.winfo_rooty() - self.winfo_rooty() + widget.winfo_height() / 2
            self.bg.burst(x, y, color=color, count=count)
        except Exception:
            pass

    def _set_all(self, checked):
        value = "on" if checked else "off"
        for item in self.row_widgets:
            item["variable"].set(value)
            if checked:
                item["checkbox"].select()
            else:
                item["checkbox"].deselect()

    # ---------- 扫描 ----------
    def start_scan(self):
        if self.scanning or self.cleaning:
            return
        # 交互粒子反馈
        self._burst_from_widget(self.btn_scan, color=C_PRIMARY_GLOW, count=24)
        self.scanning = True
        self._set_controls(False)
        self.summary_label.configure(text="正在分析…", text_color=C_WARN)
        self.metric_label.configure(text="正在统计可释放空间", text_color=C_TEXT_DIM)
        for w in self.list_container.winfo_children():
            w.destroy()
        self.row_widgets.clear()
        self.status.configure(text="正在扫描 C 盘垃圾文件（含第三方应用）…", text_color=C_TEXT_DIM)
        self.progress.set(0)
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        total = len(self.rules)
        all_count = 0
        all_size = 0
        for i, rule in enumerate(self.rules, 1):
            count, size, files = scan_rule(rule)
            rule["_count"] = count
            rule["_size"] = size
            rule["_files"] = files
            # 重置二级选择状态（v2.3.2）：None 表示未做细粒度选择，清理全部
            rule["_selected_folders"] = None
            rule["_selected_packages"] = None
            all_count += count
            all_size += size
            self.after(0, lambda r=rule: self._add_row(r))
            self.after(0, lambda v=i / total: self.progress.set(v))
        self.after(0, lambda: self._finish_scan(all_count, all_size))

    def _add_row(self, rule, selected=True):
        idx = len(self.row_widgets)
        cols = self._cols
        var = ctk.StringVar(value="on" if selected else "off")

        card = make_glass_card(self.list_container, radius=14, height=142)
        card.grid(row=idx // cols, column=idx % cols, sticky="ew", padx=6, pady=5)
        card.grid_propagate(False)
        bind_hover(card, C_GLASS, C_GLASS_HOV)

        # 左侧色条与类别图标，让不同清理项一眼可分

        icon, accent_color, category = rule_visual(rule)

        accent = ctk.CTkFrame(card, fg_color=accent_color, corner_radius=2, width=4)
        accent.pack(side="left", fill="y", padx=(0, 0))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=(8, 14), pady=8)

        # 顶行：复选框 + 名称 (左) ... 大小 (右，更突出)
        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x")

        cb = ctk.CTkCheckBox(
            top_row, text="", variable=var, onvalue="on", offvalue="off",
            width=24, checkbox_width=18, checkbox_height=18,
            fg_color=C_PRIMARY, hover_color=C_PRIMARY_HOV, corner_radius=4
        )
        cb.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            top_row, text=icon, width=22, font=fnt(17, "bold"),
            text_color=accent_color, anchor="w"
        ).pack(side="left", padx=(0, 5))

        name = ctk.CTkLabel(
            top_row, text=rule["name"],
            font=fnt(15, "bold"), text_color=C_TEXT, anchor="w"
        )
        name.pack(side="left", fill="x", expand=True)

        sz = ctk.CTkLabel(
            top_row, text=fmt_size(rule["_size"]),
            font=fnt(15, "bold"), text_color=C_SUCCESS, anchor="e"
        )
        sz.pack(side="right", padx=(8, 0))

        # 描述（wraplength 取偏小值，适配窄列；宽列下文字左对齐自然换行）
        desc = ctk.CTkLabel(
            content, text=rule["desc"],
            font=fnt(11), text_color=C_TEXT_DIM, anchor="w",
            wraplength=320, justify="left"
        )
        desc.pack(fill="x", pady=(4, 4), anchor="w")

        # 分类标签提供更清晰的扫描范围提示
        ctk.CTkLabel(
            content, text=category, font=fnt(9, "bold"), text_color=accent_color,
            fg_color=C_PANEL, corner_radius=5, padx=7, pady=2
        ).pack(anchor="w", pady=(0, 5))

        # 底行：文件数 (左) ... 详情按钮 (右)
        bottom_row = ctk.CTkFrame(content, fg_color="transparent")
        bottom_row.pack(fill="x")

        cnt = ctk.CTkLabel(
            bottom_row, text=f"📄  {rule['_count']:,} 个文件",
            font=fnt(10), text_color=C_TEXT_FAINT, anchor="w"
        )
        cnt.pack(side="left")

        if rule.get("type") == "deep":
            detail_btn = ctk.CTkButton(
                bottom_row, text="📁 查看归属", width=100, height=22,
                font=fnt(10), fg_color="transparent", border_width=1,
                border_color=C_PRIMARY, text_color=C_PRIMARY,
                hover_color=C_GLASS_HOV, corner_radius=5,
                command=lambda r=rule: self._show_deep_folder_details(r),
            )
            detail_btn.pack(side="right")
        elif rule.get("type") == "update":
            detail_btn = ctk.CTkButton(
                bottom_row, text="📦 查看安装包", width=110, height=22,
                font=fnt(10), fg_color="transparent", border_width=1,
                border_color=C_PRIMARY, text_color=C_PRIMARY,
                hover_color=C_GLASS_HOV, corner_radius=5,
                command=lambda r=rule: self._show_update_packages(r),
            )
            detail_btn.pack(side="right")

        # 「📂 打开」：在资源管理器中定位该清理项的根路径
        open_path = self._get_rule_open_path(rule)
        open_btn = ctk.CTkButton(
            bottom_row, text="📂", width=28, height=22,
            font=fnt(11), fg_color="transparent", border_width=1,
            border_color=C_GLASS_BORDER, text_color=C_TEXT_DIM,
            hover_color=C_GLASS_HOV, corner_radius=5,
            command=lambda p=open_path: open_in_explorer(p),
        )
        open_btn.pack(side="right", padx=(0, 4))

        self.row_widgets.append({"variable": var, "checkbox": cb, "rule": rule, "card": card})

    def _get_rule_open_path(self, rule):
        """取清理项用于「在资源管理器打开」的代表路径。"""
        if rule.get("paths"):
            return rule["paths"][0]
        if rule.get("roots"):
            return rule["roots"][0]
        return ""

    def _show_deep_folder_details(self, rule):
        FolderDetailDialog(self, rule)

    def _show_update_packages(self, rule):
        PackageDetailDialog(self, rule)

    def _finish_scan(self, all_count, all_size):
        self.scanning = False
        self.has_scanned = True
        self._set_controls(True)
        self.progress.set(1)
        self.summary_label.configure(
            text=f"发现 {all_count:,} 个文件",
            text_color=C_SUCCESS
        )
        self.metric_label.configure(
            text=f"预计可释放 {fmt_size(all_size)}", text_color=C_SUCCESS
        )
        if all_count == 0:
            self.status.configure(text="未发现可清理的垃圾文件，C 盘很干净 🙂", text_color=C_TEXT_DIM)
        else:
            self.status.configure(
                text=f"扫描完成：共 {all_count:,} 个文件，约 {fmt_size(all_size)} 可释放。勾选要清理的项，点击「清理选中」。",
                text_color=C_TEXT_DIM
            )

    # ---------- 清理 ----------
    def start_clean(self):
        if self.scanning or self.cleaning:
            return
        selected = [(item["variable"], item["rule"]) for item in self.row_widgets if item["variable"].get() == "on"]
        if not selected:
            mb.showwarning("提示", "请先勾选要清理的项目。")
            return
        # 按二级选择过滤出真正要清理的文件列表（v2.3.2）
        clean_plan = []  # [(rule, filtered_files), ...]
        total_count = 0
        total_size = 0
        for _, rule in selected:
            files = filter_files_by_selection(rule, rule["_files"])
            if not files:
                continue
            clean_plan.append((rule, files))
            total_count += len(files)
            total_size += sum(sz for _, sz in files)
        if not clean_plan:
            mb.showinfo("提示", "所选项目下没有可清理的文件。\n（若进入了二级详情，请确认已勾选具体清理项）")
            return
        ok = mb.askyesno("确认清理",
                         f"即将清理 {len(clean_plan)} 类项目，共 {total_count:,} 个文件，约 {fmt_size(total_size)}。\n\n"
                         "确认继续？被清理的缓存/日志/临时文件通常可自动重建；\n"
                         "少数文件可能因权限不足被跳过（建议以管理员身份运行）。")
        if not ok:
            return
        # 交互粒子反馈（橙色爆发）
        self._burst_from_widget(self.btn_clean, color=C_WARN, count=28)
        self.cleaning = True
        self._set_controls(False)
        self.status.configure(text="正在清理…", text_color=C_WARN)
        self.progress.set(0)
        threading.Thread(target=self._clean_worker, args=(clean_plan, total_count), daemon=True).start()

    def _clean_worker(self, clean_plan, total_count):
        freed = 0
        deleted = 0
        skipped = 0
        done = 0
        for rule, files in clean_plan:
            f, d, s = clean_files(files)
            freed += f
            deleted += d
            skipped += s
            done += len(files)
            self.after(0, lambda v=(done / total_count if total_count else 1): self.progress.set(v))
        self.after(0, lambda: self._finish_clean(freed, deleted, skipped, total_count))

    def _finish_clean(self, freed, deleted, skipped, total_count):
        self.cleaning = False
        self._set_controls(True)
        self.progress.set(1)
        # 清理完成时来一次绿色粒子庆祝爆发（从状态栏中心）
        try:
            x = self.winfo_width() / 2
            y = self.winfo_height() - 40
            self.bg.burst(x, y, color=C_SUCCESS, count=30)
        except Exception:
            pass
        msg = f"清理完成！已释放 {fmt_size(freed)}（删除 {deleted} 个文件）。"
        if skipped:
            msg += f"  {skipped} 个文件因权限不足被跳过（建议以管理员身份运行）。"
        self.status.configure(text=msg, text_color=C_SUCCESS)
        self.summary_label.configure(text="清理已完成", text_color=C_SUCCESS)
        self.metric_label.configure(text=f"本次释放 {fmt_size(freed)}", text_color=C_SUCCESS)
        mb.showinfo("清理完成", msg)
        self.start_scan()

    def _set_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in (self.btn_scan, self.btn_clean, self.btn_all, self.btn_none, self.btn_theme):
            b.configure(state=state)


if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()
