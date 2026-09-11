# -*- coding: utf-8 -*-
"""诊断欢迎页 list_container / box 的实际几何。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp

app = CleanerApp()

def probe():
    app.update_idletasks(); app.update()
    lc = app.list_container
    print("list_container: x=%d y=%d w=%d h=%d" % (lc.winfo_x(), lc.winfo_y(), lc.winfo_width(), lc.winfo_height()))
    print("scroll canvas: w=%d h=%d" % (app.scroll._parent_canvas.winfo_width(), app.scroll._parent_canvas.winfo_height()))
    for ch in lc.winfo_children():
        print("  child %-12s x=%d y=%d w=%d h=%d" % (ch.__class__.__name__, ch.winfo_x(), ch.winfo_y(), ch.winfo_width(), ch.winfo_height()))
    app.destroy()

app.after(1800, probe)
app.mainloop()
