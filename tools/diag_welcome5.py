# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp
app = CleanerApp()
def probe():
    app.update_idletasks(); app.update()
    s = app.scroll
    print("scroll children:")
    for ch in s.winfo_children():
        print("   ", ch.__class__.__name__, ch)
    # CTkScrollableFrame 内部结构
    print("scroll inner attrs:", [a for a in dir(s) if 'canvas' in a.lower() or 'parent' in a.lower()])
    cv = s._parent_canvas
    print("parent_canvas children:", [c.__class__.__name__ for c in cv.winfo_children()])
    print("parent_canvas geometry:", cv.winfo_width(), cv.winfo_height())
    # list_container 的 master
    print("lc master:", app.list_container.master)
    app.destroy()
app.after(2200, probe)
app.mainloop()
