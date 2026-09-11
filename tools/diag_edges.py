# -*- coding: utf-8 -*-
"""像素级边缘诊断：扫描卡片左右/上下边缘，检查是否存在外溢色带（紫边）。

原理：卡片底色是 C_GLASS(#1d2438)，描边是 C_GLASS_BORDER(#3d4d75)。
若在卡片矩形之外（即背景 #0d1018 区域内）出现 #3d4d75 / #232b42，
说明描边外溢 -> 紫边 bug 复现。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import CleanerApp
import config

app = CleanerApp()

BG = tuple(int(config.C_BG.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
GLASS = tuple(int(config.C_GLASS.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
BORDER = tuple(int(config.C_GLASS_BORDER.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
GLASS2 = tuple(int(config.C_GLASS_2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

def near(a, b, tol=10):
    return all(abs(x - y) <= tol for x, y in zip(a, b))

def check():
    app.update_idletasks(); app.update()
    if not app.row_widgets:
        print("[edge] 无卡片，跳过"); app.after(200, app.destroy); return
    card = app.row_widgets[0]["card"]
    cx, cy = card.winfo_rootx(), card.winfo_rooty()
    cw, ch = card.winfo_width(), card.winfo_height()
    print(f"[edge] 首卡 root=({cx},{cy}) size={cw}x{ch}")

    from PIL import ImageGrab
    # 抓取卡片四周 8px 缓冲带
    pad = 8
    img = ImageGrab.grab(bbox=(cx - pad, cy - pad,
                               cx + cw + pad, cy + ch + pad))
    W, H = img.size
    px = img.load()

    # 卡片在抓图里的坐标
    lx, ty = pad, pad
    rx, by = pad + cw - 1, pad + ch - 1

    bad = 0
    samples = []
    # 沿左边缘外侧的那一列像素（lx-1, lx-2）纵向扫描
    for dx in (-1, -2, 0, cw, cw + 1):
        hits = 0
        for y in range(ty + 4, by - 4, 3):
            x = lx + dx
            if 0 <= x < W:
                p = px[x, y][:3]
                if near(p, BORDER) or near(p, GLASS2, 6):
                    hits += 1
        if dx < 0:
            if hits:
                bad += hits
            samples.append(f"x=card{dx:+d} 疑似描边像素={hits}")
    # 上边缘
    for dy in (-1, -2):
        hits = 0
        for x in range(lx + 4, rx - 4, 3):
            y = ty + dy
            if 0 <= y < H:
                p = px[x, y][:3]
                if near(p, BORDER):
                    hits += 1
        if hits:
            bad += hits
        samples.append(f"y=card{dy:+d} 疑似描边像素={hits}")

    for s in samples:
        print("   ", s)

    # 采一条水平剖面，打印颜色变化序列
    ymid = ty + ch // 2
    seq = []
    for x in range(lx - 4, lx + 5):
        p = px[x, ymid][:3]
        tag = ("BG" if near(p, BG, 6) else
               "GLASS" if near(p, GLASS, 8) else
               "BORDER" if near(p, BORDER, 12) else
               "GLASS2" if near(p, GLASS2, 6) else
               "#%02x%02x%02x" % p)
        seq.append(f"{x - lx:+d}:{tag}")
    print("[edge] 左边缘剖面", " | ".join(seq))
    print("[edge] 外溢像素总数 =", bad, "->", "PASS 无紫边" if bad == 0 else "FAIL 存在紫边")
    app.after(200, app.destroy)

app.after(1200, app.start_scan)
app.after(14000, check)
app.mainloop()
