# -*- coding: utf-8 -*-
"""依次打开各对话框，验证是否正常构建 + 截图。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp
from PIL import ImageGrab

app = CleanerApp()
shots = []

def grab(win, tag):
    try:
        app.update_idletasks(); app.update()
        time.sleep(0.4)
        x, y = win.winfo_rootx(), win.winfo_rooty()
        w, h = win.winfo_width(), win.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        out = "tools/_dlg_%s.png" % tag
        img.save(out); shots.append(out)
        print("[dlg] %s -> %s %s" % (tag, out, img.size))
    except Exception as e:
        print("[dlg] %s 失败: %s" % (tag, e))

def run():
    app.update_idletasks(); app.update()
    # 1) 设置对话框
    try:
        app._open_settings()
        for w in app.winfo_children():
            if w.winfo_class() == 'Toplevel' or (hasattr(w, 'title') and '设置' in str(w.title() if hasattr(w,'title') else '')):
                grab(w, 'settings'); w.destroy(); break
    except Exception as e:
        print("settings 失败:", e)
    app.update_idletasks(); app.update()
    app.destroy()

app.after(1600, run)
app.mainloop()
print("FILES:", shots)
