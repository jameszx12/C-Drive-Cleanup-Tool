# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · 配置模块（主题令牌 / 路径 / 用户设置 / 日志）。

v4.0：颜色令牌统一由 theme.py 提供（按亮度分层的设计系统），
本模块只做「令牌装载 + 旧变量名兼容」，页面代码引用 config.C_* 即可。
"""
import os
import json
import logging

import theme as _theme

APP_NAME = "C盘垃圾清理工具"
AUTHOR = "zx"
VERSION = "v4.3.0"

FONT_FAMILY = "Microsoft YaHei UI"   # Windows 系统内置中文字体，清晰锐利
MONO_FAMILY = "Consolas"              # 等宽字体，用于路径显示

# ------------------------------------------------------------------ 颜色令牌
# 旧变量名 -> theme.py 令牌 key（保持页面代码零改动的前提下整体换肤）
_TOKEN_ALIAS = {
    "C_BG":            "BG",
    "C_BG_ALT":        "BG_ALT",
    "C_GLASS":         "SURFACE",
    "C_GLASS_HOV":     "SURFACE_HOV",
    "C_GLASS_2":       "SURFACE_2",
    "C_GLASS_3":       "SURFACE_3",
    "C_GLASS_BORDER":  "LINE_2",
    "C_GLASS_BORDER_HL": "LINE_3",
    "C_LINE":          "LINE",
    "C_LINE_2":        "LINE_2",
    "C_LINE_3":        "LINE_3",
    "C_PANEL":         "SURFACE_3",
    "C_PANEL_SOFT":    "SURFACE_2",
    "C_PRIMARY":       "PRIMARY",
    "C_PRIMARY_HOV":   "PRIMARY_HOV",
    "C_PRIMARY_SOFT":  "PRIMARY_SOFT",
    "C_PRIMARY_GLOW":  "PRIMARY",
    "C_SUCCESS":       "SUCCESS",
    "C_SUCCESS_SOFT":  "SUCCESS_SOFT",
    "C_WARN":          "WARN",
    "C_WARN_HOV":      "WARN",
    "C_WARN_SOFT":     "WARN_SOFT",
    "C_DANGER":        "DANGER",
    "C_DANGER_SOFT":   "DANGER_SOFT",
    "C_INFO":          "INFO",
    "C_TEXT":          "TEXT",
    "C_TEXT_DIM":      "TEXT_2",
    "C_TEXT_3":        "TEXT_3",
    "C_TEXT_FAINT":    "TEXT_4",
    "C_TEXT_4":        "TEXT_4",
    "C_HL":            "HL",
    # v4.3.0：particles 渐变三段别名（该模块保留供性能测试，缺失会 AttributeError）
    "C_BG_TOP":        "BG",
    "C_BG_MID":        "BG_ALT",
    "C_BG_BOT":        "SURFACE",
}


def _load_tokens(theme_name):
    """把 theme.py 的令牌展开成模块级 C_* 变量（apply_theme 时再次调用）。"""
    tk = _theme.tokens(theme_name)
    g = globals()
    for var, key in _TOKEN_ALIAS.items():
        g[var] = tk.get(key, "#000000")


# 初始为深色（apply_theme 会按用户偏好覆盖）
_load_tokens("dark")

# 粒子可选色板
PARTICLE_COLORS = ["#5b8cff", "#8b6ef5", "#2dd4a7", "#a855f7", "#06b6d4", "#38bdf8"]

# 当前主题名（apply_theme 同步更新；供图标/控件按主题选变体）
CURRENT_THEME = "dark"


def apply_theme(theme_name):
    """应用主题色令牌；调用方负责重建已创建的控件。"""
    if theme_name not in _theme.THEMES:
        raise ValueError(f"Unknown theme: {theme_name}")
    global CURRENT_THEME
    _theme.CURRENT = theme_name
    CURRENT_THEME = theme_name
    _load_tokens(theme_name)


def env(name, default=""):
    return os.environ.get(name, default)


def detect_system_theme():
    """检测系统当前主题（深色 / 浅色）。darkdetect 不可用时回落 dark。"""
    try:
        import darkdetect
        return "dark" if darkdetect.isDark() else "light"
    except Exception:
        return "dark"


LOCAL = env("LOCALAPPDATA", "")
APP = env("APPDATA", "")
PF = env("PROGRAMFILES", r"C:\Program Files")
PFX = env("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
PD = env("PROGRAMDATA", r"C:\ProgramData")
HOME = env("USERPROFILE", r"C:\Users")

# ---------- 配置持久化 ----------
# 用户设置存于 %LocalAppData%\C盘清理工具\settings.json（exe 以管理员运行，
# 写系统目录不可靠，LocalAppData 无权限问题）
CONFIG_DIR = os.path.join(env("LOCALAPPDATA", ""), "C盘清理工具")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")
DEFAULT_CONFIG = {
    "recycle_mode": False,   # 删除到回收站（可恢复，空间不立即释放）
    "theme": "dark",
    # v4.0：窗口毛玻璃默认关闭。它是「卡片彩色边缘」的放大器 ——
    # 配合 -transparentcolor，任何 1px 圆角绘制外溢都会作为彩色描边暴露。
    # 关闭后窗口为纯色不透明背景，边缘干净平滑。
    "glass_mode": False,
}


def load_config():
    """读取用户配置；文件缺失/损坏时回退默认值。"""
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
    except Exception:
        pass
    return cfg


def save_config(cfg):
    """写入用户配置；失败静默（不影响主流程）。"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------- 日志 ----------
# 记录扫描/清理结果与删除失败明细，便于用户回溯与报 bug
_logger = logging.getLogger("cleaner")
_logging_ready = False


def init_logging():
    global _logging_ready
    if _logging_ready:
        return
    _logging_ready = True
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        h = logging.FileHandler(os.path.join(CONFIG_DIR, "cleaner.log"),
                                encoding="utf-8")
        h.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        _logger.addHandler(h)
        _logger.setLevel(logging.INFO)
        _logger.propagate = False
    except Exception:
        pass


init_logging()


def _hex_rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
