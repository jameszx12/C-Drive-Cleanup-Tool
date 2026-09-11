# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp
app = CleanerApp()
def probe():
    app.update_idletasks(); app.update()
    cv = app.scroll._parent_canvas
    print("canvas w=%d h=%d" % (cv.winfo_width(), cv.winfo_height()))
    print("scroll frame w=%d h=%d" % (app.scroll.winfo_width(), app.scroll.winfo_height()))
    print("welcome_h cached =", app._welcome_h)
    print("lc h =", app.list_container.winfo_height())
    print("lc size req =", app.list_container.winfo_reqheight())
    # 手动再跑一次 configure 逻辑
    ch = cv.winfo_height()
    app.list_container.configure(height=ch)
    app.update_idletasks(); app.update()
    print("after force -> lc h =", app.list_container.winfo_height())
    app.destroy()
app.after(2500, probe)
app.mainloop()
