# -*- coding: utf-8 -*-
"""视觉截图：欢迎页 + 扫描后（卡片网格）两张。

用法：python tools/shot.py [welcome|scan|both]
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import CleanerApp
mode = (sys.argv[1] if len(sys.argv) > 1 else "both")

app = CleanerApp()


def grab(tag):
    try:
        from PIL import ImageGrab
        app.update_idletasks(); app.update()
        time.sleep(0.35)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        out = f"tools/_v4_{tag}.png"
        img.save(out)
        print(f"[shot] {out} {img.size}")
    except Exception as e:
        print("[shot] 失败:", e)


def step():
    if mode in ("welcome", "both"):
        grab("welcome")
    if mode in ("scan", "both"):
        app.start_scan()
        app.after(15000, after_scan)
    else:
        app.after(300, app.destroy)


def after_scan():
    grab("scan")
    print("[shot] 卡片数:", len(app.row_widgets))
    app.after(300, app.destroy)


app.after(1500, step)
app.mainloop()
