# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · 图标模块（应用图标提取与内置图标加载）。"""
import os
import sys
import glob
import struct
import zlib
import ctypes
from ctypes import wintypes

from config import LOCAL, APP

_SHELL32 = r"C:\Windows\System32\shell32.dll"
_CLEANMGR = r"C:\Windows\System32\cleanmgr.exe"
APP_EXE_CANDIDATES = {
    # ---- 系统类（使用 Windows 自带工具图标）----
    "win_temp": [_CLEANMGR, _SHELL32 + ":15"],
    "user_temp": [_CLEANMGR, _SHELL32 + ":15"],
    "recycle": [_SHELL32 + ":32", _SHELL32 + ":31"],
    "prefetch": [_CLEANMGR, _SHELL32 + ":24"],
    "wsus": [_CLEANMGR, _SHELL32 + ":24"],
    "delivery": [_CLEANMGR, _SHELL32 + ":24"],
    "thumb": [r"C:\Windows\explorer.exe", _SHELL32 + ":15"],
    "wer": [_CLEANMGR, _SHELL32 + ":24"],
    "winlogs": [_CLEANMGR, _SHELL32 + ":24"],
    "crashdumps": [_CLEANMGR, _SHELL32 + ":24"],
    # ---- 浏览器 ----
    "chrome_cache": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                     r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                     os.path.join(LOCAL, "Google", "Chrome", "Application", "chrome.exe")],
    "edge_cache": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                   r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
    "firefox_cache": [r"C:\Program Files\Mozilla Firefox\firefox.exe",
                      r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"],
    "opera_cache": [r"C:\Program Files\Opera\launcher.exe",
                    r"C:\Program Files (x86)\Opera\launcher.exe",
                    r"C:\Program Files\Opera\opera.exe"],
    "brave_cache": [r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                    os.path.join(LOCAL, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")],
    # ---- 通讯 / 协作 ----
    "discord": [os.path.join(LOCAL, "Discord", "app-*", "Discord.exe")],
    "slack": [os.path.join(LOCAL, "slack", "slack.exe"), os.path.join(APP, "slack", "slack.exe")],
    "teams": [os.path.join(LOCAL, "Microsoft", "Teams", "current", "Teams.exe"),
              r"C:\Program Files\Microsoft\Teams\current\Teams.exe"],
    "wechat": [r"C:\Program Files\Tencent\WeChat\WeChat.exe",
               r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
               r"C:\Program Files\Tencent\Weixin\Weixin.exe"],
    # ---- 开发工具 ----
    "vscode": [os.path.join(LOCAL, "Programs", "Microsoft VS Code", "Code.exe")],
    "jetbrains": [os.path.join(LOCAL, "JetBrains", "Toolbox", "apps", "*", "*", "bin", "*.exe")],
    "android_studio": [r"C:\Program Files\Android\Android Studio\bin\studio64.exe"],
    "npm_cache": [r"C:\Program Files\nodejs\node.exe",
                  os.path.join(LOCAL, "Programs", "nodejs", "node.exe")],
    "pip_cache": [os.path.join(LOCAL, "Programs", "Python", "Python*", "python.exe"),
                  r"C:\Python*\python.exe"],
    # ---- 游戏平台 ----
    "steam": [r"C:\Program Files\Steam\steam.exe", r"C:\Program Files (x86)\Steam\steam.exe"],
    "epic": [r"C:\Program Files\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe"],
    "ea_origin": [r"C:\Program Files (x86)\Origin\Origin.exe", r"C:\Program Files\Origin\Origin.exe"],
    "ubisoft": [r"C:\Program Files\Ubisoft\Ubisoft Game Launcher\upc.exe"],
    "gog": [r"C:\Program Files\GOG Galaxy\GalaxyClient.exe",
            r"C:\Program Files (x86)\GOG Galaxy\GalaxyClient.exe"],
    "battlenet": [r"C:\Program Files\Battle.net\Battle.net.exe",
                  r"C:\Program Files (x86)\Battle.net\Battle.net.exe"],
    # ---- 媒体 / 设计 ----
    "adobe_mediacache": [r"C:\Program Files\Adobe\Adobe Premiere Pro*\Adobe Premiere Pro.exe",
                         r"C:\Program Files\Adobe\Adobe Photoshop*\Photoshop.exe"],
    "adobe_logs": [r"C:\Program Files\Adobe\Adobe Premiere Pro*\Adobe Premiere Pro.exe",
                   r"C:\Program Files\Adobe\Adobe Photoshop*\Photoshop.exe"],
    "spotify": [os.path.join(APP, "Spotify", "Spotify.exe"),
                os.path.join(LOCAL, "Spotify", "Spotify.exe")],
    "obs": [r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
            r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe"],
    # ---- 云盘 ----
    "dropbox": [os.path.join(LOCAL, "Dropbox", "Dropbox.exe"), os.path.join(APP, "Dropbox", "Dropbox.exe")],
    "baidu": [os.path.join(LOCAL, "baidu", "BaiduNetdisk", "BaiduNetdisk.exe")],
    "onedrive_logs": [os.path.join(LOCAL, "Microsoft", "OneDrive", "OneDrive.exe")],
    # ---- 驱动 / 显卡 ----
    "nvidia": [r"C:\Program Files\NVIDIA Corporation\NVIDIA app\CEF\NVIDIA App.exe",
               r"C:\Program Files\NVIDIA Corporation\NVIDIA GeForce Experience\NVIDIA GeForce Experience.exe"],
    "amd": [r"C:\Program Files\AMD\CNext\CNext.exe",
            r"C:\Program Files\AMD\CNext\CCD\CNCNext.exe"],
    "intel": [r"C:\Program Files\Intel\Intel(R) Arc Control\ArcControl.exe",
              r"C:\Windows\System32\igfxTray.exe"],
}


def _parse_icon_candidate(cand):
    """解析候选：返回 (路径, 索引)。支持 'dll:索引' 形式。"""
    # 仅当冒号后是纯数字时视为索引（避免盘符 'C:\' 误判）
    if ":" in cand:
        path, _, tail = cand.rpartition(":")
        if tail.isdigit():
            return path, int(tail)
    return cand, 0


def find_app_exe(key):
    """根据清理项 key 找到已安装应用的可执行文件；未安装返回 None。"""
    for cand in APP_EXE_CANDIDATES.get(key, []):
        path, _ = _parse_icon_candidate(cand)
        try:
            for p in glob.glob(path):
                if os.path.isfile(p):
                    return p
        except Exception:
            continue
    return None


def _png_encode(width, height, rgba):
    """把 RGBA 像素编码为 PNG 字节（纯标准库，zlib 压缩）。"""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        return c
    raw = b""
    stride = width * 4
    for y in range(height):
        raw += b"\x00" + rgba[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _hicon_to_rgba(hicon):
    """HICON → RGBA 像素字节（bytes）。失败返回 None。"""
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        user32.GetIconInfo.restype = wintypes.BOOL
        user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.c_void_p]
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.restype = ctypes.c_int
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.DestroyIcon.restype = wintypes.BOOL
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        gdi32.GetObjectW.restype = ctypes.c_int
        gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
        gdi32.GetDIBits.restype = ctypes.c_int
        gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                    wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                    wintypes.UINT]

        class ICONINFO(ctypes.Structure):
            _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
                        ("yHotspot", wintypes.DWORD), ("hbmMask", wintypes.HBITMAP),
                        ("hbmColor", wintypes.HBITMAP)]
        ii = ICONINFO()
        if not user32.GetIconInfo(hicon, ctypes.byref(ii)):
            return None
        hbm = ii.hbmColor or ii.hbmMask
        class BITMAP(ctypes.Structure):
            _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long),
                        ("bmHeight", ctypes.c_long), ("bmWidthBytes", ctypes.c_long),
                        ("bmPlanes", ctypes.c_ushort), ("bmBitsPixel", ctypes.c_ushort),
                        ("bmBits", ctypes.c_void_p)]
        bmp = BITMAP()
        gdi32.GetObjectW(hbm, ctypes.sizeof(BITMAP), ctypes.byref(bmp))
        w, h = max(1, bmp.bmWidth), max(1, bmp.bmHeight)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                        ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]
        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = ctypes.create_string_buffer(w * h * 4)
        hdc = user32.GetDC(0)
        try:
            got = gdi32.GetDIBits(hdc, hbm, 0, h, buf, ctypes.byref(bmi), 0)
        finally:
            user32.ReleaseDC(0, hdc)
        if got == 0:
            return None
        raw = bytearray(buf.raw)
        for i in range(0, len(raw), 4):
            raw[i], raw[i + 2] = raw[i + 2], raw[i]
        return bytes(raw), w, h
    except Exception:
        return None


def _load_shell_hicon(path, icon_index, size):
    """LoadLibrary+LoadImage 取指定尺寸原生图标（shell32/imageres 等通用库支持高分辨率）。
    返回 HICON（调用方负责 DestroyIcon），失败返回 None。
    """
    try:
        k32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        k32.LoadLibraryExW.restype = wintypes.HMODULE
        k32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
        k32.FreeLibrary.restype = wintypes.BOOL
        k32.FreeLibrary.argtypes = [wintypes.HMODULE]
        user32.LoadImageW.restype = wintypes.HICON
        user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.DestroyIcon.restype = wintypes.BOOL
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        hmod = k32.LoadLibraryExW(path, None, 0)
        if not hmod:
            return None
        try:
            h = user32.LoadImageW(hmod,
                                  ctypes.cast(ctypes.c_void_p(icon_index), wintypes.LPCWSTR),
                                  1,  # IMAGE_ICON
                                  size, size, 0)
            return h if h else None
        finally:
            k32.FreeLibrary(hmod)
    except Exception:
        return None


def _scale_bilinear(rgba, src_w, src_h, dst_size):
    """RGBA 字节 → dst_size×dst_size 双线性缩放（纯标准库，比最近邻显著平滑）。"""
    if src_w == dst_size and src_h == dst_size:
        return rgba, dst_size, dst_size
    out = bytearray(dst_size * dst_size * 4)
    x_ratio = src_w / dst_size
    y_ratio = src_h / dst_size
    for yy in range(dst_size):
        fy = (yy + 0.5) * y_ratio - 0.5
        y0 = max(0, int(fy))
        y1 = min(src_h - 1, y0 + 1)
        wy = fy - y0
        for xx in range(dst_size):
            fx = (xx + 0.5) * x_ratio - 0.5
            x0 = max(0, int(fx))
            x1 = min(src_w - 1, x0 + 1)
            wx = fx - x0
            src00 = (y0 * src_w + x0) * 4
            src01 = (y0 * src_w + x1) * 4
            src10 = (y1 * src_w + x0) * 4
            src11 = (y1 * src_w + x1) * 4
            dst = (yy * dst_size + xx) * 4
            w00 = (1 - wx) * (1 - wy)
            w01 = wx * (1 - wy)
            w10 = (1 - wx) * wy
            w11 = wx * wy
            for c in range(4):
                v = (rgba[src00 + c] * w00 + rgba[src01 + c] * w01 +
                     rgba[src10 + c] * w10 + rgba[src11 + c] * w11)
                out[dst + c] = max(0, min(255, int(v + 0.5)))
    return bytes(out), dst_size, dst_size


def extract_app_icon_png(exe_path, size=64, icon_index=0):
    """
    从 exe/dll 提取应用图标并编码为 PNG 字节。
    优先尝试 LoadLibrary+LoadImage 取原生指定尺寸（shell32/imageres 等有 256 PNG）；
    否则回退 ExtractIconExW（16/32，cleanmgr.exe 等老资源）。缩放使用双线性。
    icon_index：资源索引（shell32.dll 等系统库的图标索引，如 31=回收站空 / 32=回收站满）。
    失败返回 None（保持原字符图标）。
    """
    hicon = None
    try:
        # 路径 1：优先 LoadLibrary+LoadImage 取指定大小原生图标
        hicon = _load_shell_hicon(exe_path, icon_index, size)
        rgba_info = _hicon_to_rgba(hicon) if hicon else None
        if rgba_info:
            rgba, w, h = rgba_info
            rgba, w, h = _scale_bilinear(rgba, w, h, size)
            return _png_encode(w, h, rgba)
        if hicon:
            try:
                ctypes.windll.user32.DestroyIcon(hicon)
            except Exception:
                pass
            hicon = None
        # 路径 2：回退 ExtractIconExW（cleanmgr.exe 等老资源仅 16/32）
        shell32 = ctypes.windll.shell32
        shell32.ExtractIconExW.restype = wintypes.UINT
        shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                           ctypes.POINTER(wintypes.HICON),
                                           ctypes.POINTER(wintypes.HICON), wintypes.UINT]
        large = (wintypes.HICON * 1)()
        small = (wintypes.HICON * 1)()
        n = shell32.ExtractIconExW(exe_path, icon_index, large, small, 1)
        if n == 0 or not large[0]:
            return None
        hicon = large[0]
        rgba_info = _hicon_to_rgba(hicon)
        if not rgba_info:
            return None
        rgba, w, h = rgba_info
        rgba, w, h = _scale_bilinear(rgba, w, h, size)
        return _png_encode(w, h, rgba)
    except Exception:
        return None
    finally:
        if hicon:
            try:
                ctypes.windll.user32.DestroyIcon(hicon)
            except Exception:
                pass


# 图标缓存：{rule_key: (source_path, png_bytes)}，避免重复提取
_app_icon_cache = {}


def resource_dir():
    """返回打包后的资源目录（PyInstaller 解包路径）或源码 icons/ 目录。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "icons")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def _resource_dir():
    """同 resource_dir（内部兼容别名）。"""
    return resource_dir()


def _read_bundled_icon(key):
    """读取打包进 exe 的图标 PNG 字节；无则返回 None。"""
    p = os.path.join(_resource_dir(), key + ".png")
    try:
        if os.path.isfile(p):
            with open(p, "rb") as f:
                return f.read()
    except Exception:
        pass
    return None


def get_app_icon(key):
    """
    获取清理项对应的应用图标 PNG 字节（优先读取打包进 exe 的内置图标，
    未内置时回退到从本机已安装应用 exe 提取）。无则返回 None。
    """
    if key in _app_icon_cache:
        return _app_icon_cache[key][1]
    # 1) 内置图标资源（跨机器可用，v2.4.3）
    bundled = _read_bundled_icon(key)
    if bundled:
        _app_icon_cache[key] = ("bundled:" + key, bundled)
        return bundled
    # 2) 回退：本机 exe / dll 图标提取（仅对未内置的 key 生效）
    src_path = None
    icon_index = 0
    for cand in APP_EXE_CANDIDATES.get(key, []):
        path, idx = _parse_icon_candidate(cand)
        try:
            for p in glob.glob(path):
                if os.path.isfile(p):
                    src_path, icon_index = p, idx
                    break
        except Exception:
            continue
        if src_path:
            break
    if not src_path:
        _app_icon_cache[key] = (None, None)
        return None
    png = extract_app_icon_png(src_path, icon_index=icon_index)
    _app_icon_cache[key] = (src_path, png)
    return png


# ---------- 文件夹归属详情对话框（分页 + 搜索 + 异步渲染 + 毛玻璃风格） ----------
