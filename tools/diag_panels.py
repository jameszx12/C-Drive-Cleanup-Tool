# -*- coding: utf-8 -*-
"""面板边缘检测：对头部 / 侧边栏 / 工具栏 / 状态栏四个大面板做外溢扫描。

这些面板都用 draw_card_shell 自绘描边。若描边外溢，会在面板外的 BG 区域
出现 LINE_2(#2f3b58) 或 SURFACE_2(#1b2438) 色，表现为一圈淡紫/淡蓝边。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import CleanerApp
import config
app = CleanerApp()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


BG = rgb(config.C_BG)
S2 = rgb(config.C_GLASS_2)
LN = rgb(config.C_GLASS_BORDER)     # #2f3b58
SURF = rgb(config.C_GLASS)


def near(a, b, tol=8):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def scan(tag, w):
    from PIL import ImageGrab
    app.update_idletasks(); app.update()
    x, y = w.winfo_rootx(), w.winfo_rooty()
    W, H = w.winfo_width(), w.winfo_height()
    if W < 40 or H < 20:
        print("[E] %-12s 尺寸过小 %dx%d" % (tag, W, H)); return
    pad = 5
    img = ImageGrab.grab(bbox=(x - pad, y - pad, x + W + pad, y + H + pad))
    px = img.load()
    bad = 0
    detail = []
    # 左/右两边外侧一列
    for dx in (-1, -2):
        hits = 0
        for yy in range(pad + 6, pad + H - 6, 2):
            xx = pad + dx
            if 0 <= xx < img.size[0] and 0 <= yy < img.size[1]:
                p = px[xx, yy][:3]
                if near(p, LN, 6) or near(p, S2, 5):
                    hits += 1
        bad += hits
        if hits:
            detail.append(f"左{dx}:{hits}")
    # 上/下两边外侧一行
    for dy in (-1, -2):
        hits = 0
        for xx in range(pad + 6, pad + W - 6, 2):
            yy = pad + dy
            if 0 <= xx < img.size[0] and 0 <= yy < img.size[1]:
                p = px[xx, yy][:3]
                if near(p, LN, 6) or near(p, S2, 5):
                    hits += 1
        bad += hits
        if hits:
            detail.append(f"上{dy}:{hits}")
    status = "PASS" if bad == 0 else "溢出 " + " ".join(detail)
    print("[E] %-12s %4dx%-4d 外溢=%-4d %s" % (tag, W, H, bad, status))


def run():
    scan("header", app.btn_theme.master.master)
    scan("sidebar", app.search_entry.master.master.master
         if hasattr(app.search_entry.master, "master") else app.search_entry.master)
    scan("toolbar", app.btn_scan.master.master.master)
    scan("status", app.progress.master.master)
    app.after(200, app.destroy)


app.after(2000, run)
app.mainloop()
