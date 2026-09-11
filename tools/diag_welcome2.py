# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp
app = CleanerApp()
def probe():
    app.update_idletasks(); app.update()
    lc = app.list_container
    print("lc w,h =", lc.winfo_width(), lc.winfo_height())
    print("lc grid weights:", [lc.grid_columnconfigure(c, 'weight') for c in range(4)])
    print("lc row weights:", [lc.grid_rowconfigure(r, 'weight') for r in range(4)])
    print("lc propagate:", lc.grid_propagate(), "| pack_propagate:", lc.pack_propagate())
    # 容器父级（scroll 内部 canvas）
    par = lc.master
    print("parent:", par.__class__.__name__, par.winfo_width(), par.winfo_height())
    app.destroy()
app.after(1800, probe)
app.mainloop()
