# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import CleanerApp
app = CleanerApp()
def probe():
    app.update_idletasks(); app.update()
    lc = app.list_container
    print("lc      h=%d  (canvas h=%d)" % (lc.winfo_height(), app.scroll._parent_canvas.winfo_height()))
    for ch in lc.winfo_children():
        print("  inner x=%d y=%d w=%d h=%d  bottom=%d" % (
            ch.winfo_x(), ch.winfo_y(), ch.winfo_width(), ch.winfo_height(),
            ch.winfo_y() + ch.winfo_height()))
    app.destroy()
app.after(2000, probe)
app.mainloop()
