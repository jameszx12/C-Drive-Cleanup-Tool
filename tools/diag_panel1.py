# -*- coding: utf-8 -*-
"""精确定位：对有问题的面板做逐像素剖面，找出外溢像素的真实来源。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import CleanerApp
import config
app = CleanerApp()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def name_of(p):
    table = {
        rgb(config.C_BG): "BG",
        rgb(config.C_BG_ALT): "BG_ALT",
        rgb(config.C_GLASS): "SURFACE",
        rgb(config.C_GLASS_2): "S2",
        rgb(config.C_GLASS_3): "S3",
        rgb(config.C_GLASS_BORDER): "LINE2",
        rgb(config.C_LINE_3): "LINE3",
    }
    best, bd = None, 999
    for c, n in table.items():
        d = sum(abs(a - b) for a, b in zip(p, c))
        if d < bd:
            bd, best = d, n
    return best if bd <= 20 else "#%02x%02x%02x" % p


def run():
    from PIL import ImageGrab
    app.update_idletasks(); app.update()
    sb = app.progress.master.master          # 状态栏面板
    x, y = sb.winfo_rootx(), sb.winfo_rooty()
    W, H = sb.winfo_width(), sb.winfo_height()
    print("[P] 状态栏 root=(%d,%d) size=%dx%d" % (x, y, W, H))
    img = ImageGrab.grab(bbox=(x, y - 6, x + W, y + H + 4))
    px = img.load()
    # 竖直剖面：从面板上方 6px 到面板内 6px，取中间一列
    col = W // 2
    seq = []
    for dy in range(0, 12):
        seq.append("%+d:%s" % (dy - 6, name_of(px[col, dy][:3])))
    print("[P] 上边界竖直剖面:", " | ".join(seq))
    # 水平剖面：左边界
    row = H // 2
    seq2 = []
    for dx in range(0, 8):
        seq2.append("%+d:%s" % (dx - 6, name_of(px[dx, row + 6][:3])))
    print("[P] 左边界水平剖面:", " | ".join(seq2))
    app.after(200, app.destroy)


app.after(2000, run)
app.mainloop()
