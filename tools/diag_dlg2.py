# -*- coding: utf-8 -*-
"""打开设置对话框并截全屏局部（按对话框自身坐标）。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp
from PIL import ImageGrab
import customtkinter as ctk

app = CleanerApp()
holder = {}

def run():
    app.update_idletasks(); app.update()
    app._open_settings()
    app.update_idletasks(); app.update()
    time.sleep(0.5)
    # 找所有 Toplevel
    tl = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
    print("Toplevel:", len(tl))
    for w in tl:
        app.update_idletasks(); app.update()
        time.sleep(0.3)
        x, y, ww, hh = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
        print("  geom x=%d y=%d w=%d h=%d" % (x, y, ww, hh))
        if ww < 10 or hh < 10:
            continue
        img = ImageGrab.grab(bbox=(x, y, x+ww, y+hh))
        img.save("tools/_dlg2_settings.png")
        print("  saved tools/_dlg2_settings.png", img.size)
        break
    app.after(200, app.destroy)

app.after(1500, run)
app.mainloop()
