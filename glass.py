# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · Windows Acrylic/Mica 毛玻璃背景（iOS 风格半透明）。

给 Tk 窗口应用系统级毛玻璃：模糊窗口背后的内容并叠加色调，
配合窗口抠图透明色，实现「透过窗口看到背后应用」的 iOS 质感。

兼容性：
- Win11 22H2+：DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE=3)（transient
  window，acrylic 风格），普通窗口生效
- 其余系统：SetWindowCompositionAttribute(ACCENT_ENABLE_ACRYLICBLURBEHIND)
- 两者都失败时返回 False，调用方回退纯色背景
"""
import ctypes
import sys
from ctypes import wintypes

from config import _logger

# Tk 窗口抠图透明键色（-transparentcolor）：选一个与任何主题色都不同的极端色，
# 避免误伤控件；窗口背景像素为该色时完全透明，露出系统毛玻璃层
TRANSPARENT_KEY = "#FF00FE"

_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
_WCA_ACCENT_POLICY = 19
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMSBT_TRANSIENTWINDOW = 3


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int)]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t)]


def _top_hwnd(tk_window):
    """取 Tk 窗口真正的顶层 HWND。

    注意：Tk 的 winfo_id() 返回的是内部子窗口句柄，DWM/WCA 等系统 API
    需要顶层窗口句柄（GetAncestor GA_ROOT）。
    """
    try:
        h = int(tk_window.winfo_id())
        if not h:
            return 0
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        top = user32.GetAncestor(h, 2)   # GA_ROOT = 2
        return top or h
    except Exception:
        return 0


def apply_acrylic(tk_window, tint_rgb, alpha=0x9C):
    """
    给窗口应用毛玻璃效果。

    参数：
      tk_window  Tk/CTk 窗口对象
      tint_rgb  着色底色（如 "#161b2b"），会与模糊后的背景混合
      alpha     着色不透明度 0-255（0x9C≈61%：背后内容透出较明显；
                数值越小越透明）

    返回 True 表示系统级毛玻璃已应用；False 表示当前系统不支持。
    """
    hwnd = _top_hwnd(tk_window)
    if not hwnd or sys.platform != "win32":
        return False
    # 1) Win11 22H2+：DWM transient window backdrop（acrylic 风格）
    try:
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                              ctypes.c_void_p, wintypes.DWORD]
        backdrop = ctypes.c_int(_DWMSBT_TRANSIENTWINDOW)
        if dwm.DwmSetWindowAttribute(hwnd, _DWMWA_SYSTEMBACKDROP_TYPE,
                                     ctypes.byref(backdrop),
                                     ctypes.sizeof(backdrop)) == 0:
            _logger.info("毛玻璃: Win11 DWM backdrop 已应用 (hwnd=%s)", hwnd)
            return True
    except Exception:
        pass
    # 2) Win10 / 早期 Win11：SetWindowCompositionAttribute acrylic
    try:
        h = tint_rgb.lstrip("#")
        r, g, b = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = ((int(alpha) & 0xFF) << 24) | (b << 16) | (g << 8) | r
        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.addressof(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        user32 = ctypes.windll.user32
        user32.SetWindowCompositionAttribute.argtypes = [wintypes.HWND, ctypes.c_void_p]
        ok = bool(user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data)))
        if ok:
            _logger.info("毛玻璃: Win10 acrylic 已应用 (hwnd=%s)", hwnd)
        return ok
    except Exception:
        return False


def make_window_transparent(tk_window):
    """把窗口背景设为抠图透明键色（配合 apply_acrylic 露出毛玻璃）。

    兼容 CTk（fg_color）与原生 tk（bg）两种窗口。
    """
    try:
        try:
            tk_window.configure(fg_color=TRANSPARENT_KEY)   # customtkinter
        except Exception:
            tk_window.configure(bg=TRANSPARENT_KEY)         # 原生 tk
        tk_window.attributes("-transparentcolor", TRANSPARENT_KEY)
        return True
    except Exception:
        return False


def clear_window_transparent(tk_window):
    """取消窗口透明（回退纯色背景）。"""
    try:
        tk_window.attributes("-transparentcolor", "")
    except Exception:
        pass


def apply_window_backdrop(tk_window, tint_rgb, glass_mode=True):
    """
    窗口级毛玻璃应用入口。

    优先级：
      1. 系统级毛玻璃（DWM/Win10 acrylic）+ 窗口背景透明 → 真毛玻璃，模糊背后内容
      2. 系统不支持 → 回退不透明纯色背景（不再使用 -alpha 整体半透明兜底：
         整体半透明会让所有控件（含文字）一起变淡，可读性下降且在高刷屏上
         合成开销更大，v3.0.5 移除）
      3. glass_mode 关闭 → 恢复不透明纯色背景

    返回 True 表示窗口已具备半透明效果。

    v3.0.5 关键修复（紫色边缘）：
      之前 ``apply_acrylic`` 在 Win11 上会返回 True（DWM backdrop 调用成功），
      但 Tk 的 ``-transparentcolor`` 抠图对 Web layered 窗口并不总能生效，
      结果窗口内出现一圈未抠净的合成色 —— 深色主题下正是偏紫的灰蓝，
      与卡片圆角外溢叠加后就是用户看到的「紫色边缘」。
      现在：只有**确认** transparentcolor 生效时才保留毛玻璃；
      否则立即回退纯色，保证边缘干净。
    """
    if not glass_mode:
        clear_window_transparent(tk_window)
        try:
            tk_window.attributes("-alpha", 1.0)
            tk_window.configure(fg_color=tint_rgb)
        except Exception:
            pass
        return False

    applied = False
    try:
        applied = apply_acrylic(tk_window, tint_rgb)
    except Exception:
        applied = False

    if applied:
        if make_window_transparent(tk_window):
            # 透明度键已设置：校验是否真的生效（读回 -transparentcolor）
            if _verify_transparent_key(tk_window):
                return True
        # 毛玻璃已应用但抠图不可靠 → 回退纯色，避免合成色边缘
        _logger.info("毛玻璃: transparentcolor 未生效，回退不透明纯色")
        clear_window_transparent(tk_window)

    try:
        tk_window.attributes("-alpha", 1.0)
        tk_window.configure(fg_color=tint_rgb)
    except Exception:
        pass
    return False


def _verify_transparent_key(tk_window):
    """校验 -transparentcolor 是否真的被窗口管理器接受。

    某些 Windows 配置（DWM backdrop 的 layered 窗口）会静默忽略该属性，
    读回值不为空即可认为已设置；读不到时保守返回 False 走纯色回退。
    """
    try:
        cur = tk_window.attributes("-transparentcolor")
        return bool(cur) and str(cur).lower() == TRANSPARENT_KEY.lower()
    except Exception:
        return False
