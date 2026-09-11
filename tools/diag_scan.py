# -*- coding: utf-8 -*-
"""诊断脚本：启动主窗口 -> 自动扫描 -> 截图 + 边缘像素校验。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import CleanerApp
app = CleanerApp()
RESULT = {}

def after_scan():
    app.update_idletasks()
    app.update()
    try:
        from PIL import ImageGrab
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        img.save("tools/_diag_scan.png")
        print("[diag] 截图:", "tools/_diag_scan.png", img.size)
    except Exception as e:
        print("[diag] 截图失败:", e)
    print("[diag] 卡片数:", len(app.row_widgets))
    for it in app.row_widgets[:2]:
        card = it["card"]; cv = card._canvas
        print("[diag] card", card.winfo_width(), card.winfo_height(),
              "radius=", card.cget("corner_radius"),
              "bw=", card.cget("border_width"))
        print("[diag]   glass_border:", cv.find_withtag("glass_border"),
              "sel_bar:", cv.find_withtag("sel_bar"))
    app.after(300, app.destroy)

def kick():
    app.start_scan()
    app.after(14000, after_scan)

app.after(1200, kick)
app.mainloop()
