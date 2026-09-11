#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 cpp/src/icons_data.cpp —— 从 icons/ 目录提取 PNG 转 C 字节数组。
用法：D:/miniconda3/python.exe tools/make_cpp_icons.py
输出：cpp/src/icons_data.cpp（规则图标 + 分类导航图标 + 对话框图标，dark 变体）
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根
ICONS = os.path.join(ROOT, "icons")
OUT = os.path.join(ROOT, "cpp", "src", "icons_data.cpp")

RULE_KEYS = [
    "win_temp", "user_temp", "recycle", "prefetch", "wsus", "delivery",
    "thumb", "wer", "winlogs", "crashdumps", "chrome_cache", "edge_cache",
    "firefox_cache", "opera_cache", "brave_cache", "discord", "slack",
    "teams", "wechat", "vscode", "jetbrains", "npm_cache", "pip_cache",
    "android_studio", "steam", "epic", "ea_origin", "ubisoft", "gog",
    "battlenet", "adobe_mediacache", "adobe_logs", "spotify", "obs",
    "dropbox", "baidu", "onedrive_logs", "nvidia", "amd", "intel",
    "deep_apps", "update_packages",
]
NAV_KEYS = ["all", "system", "browser", "app", "dev", "game",
            "media", "cloud", "driver", "deep", "update"]
DIALOG_KEYS = ["settings", "scan", "clean", "safe", "cancel", "check",
               "expand", "collapse", "folder", "file", "pkg", "prev",
               "next", "power", "invert", "search_clear", "sun", "moon"]


def collect():
    entries = []
    for k in RULE_KEYS:
        p = os.path.join(ICONS, k + ".png")
        if os.path.exists(p):
            entries.append((k, p))
    for k in NAV_KEYS:
        p = os.path.join(ICONS, "ui", "d_nav_%s_24.png" % k)
        if os.path.exists(p):
            entries.append(("nav_" + k, p))
    for k in DIALOG_KEYS:
        p = os.path.join(ICONS, "ui", "d_%s_24.png" % k)
        if os.path.exists(p):
            entries.append((k, p))
    return entries


def c_name(name):
    return "ic_" + name.replace("-", "_")


def main():
    entries = collect()
    lines = ["// icons_data.cpp - 自动生成（tools/make_cpp_icons.py），请勿手改",
             "#include \"ui_icons.h\"", ""]
    for name, path in entries:
        data = open(path, "rb").read()
        arr = "static const unsigned char %s[] = {" % c_name(name)
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            arr += ",".join(str(b) for b in chunk) + ","
        arr += "};"
        lines.append(arr)
        lines.append("")
    lines.append("const IconData ICONS[] = {")
    for name, path in entries:
        lines.append('    {"%s", %s, %d},' % (name, c_name(name),
                                              os.path.getsize(path)))
    lines.append("};")
    lines.append("const int ICON_COUNT = %d;" % len(entries))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("generated %d icons -> %s" % (len(entries), OUT))
    print("missing rules:", sorted(set(RULE_KEYS) -
                                   {n for n, _ in entries}))


if __name__ == "__main__":
    main()
