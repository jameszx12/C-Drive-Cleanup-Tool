# -*- coding: utf-8 -*-
"""布局诊断：打印关键控件的实际尺寸，定位被压扁/裁切的元素。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import CleanerApp
app = CleanerApp()


def report():
    app.update_idletasks(); app.update()

    def dump(label, w):
        try:
            print("[L] %-22s %4d x %-4d  mapped=%s  y=%d h=%d"
                  % (label, w.winfo_width(), w.winfo_height(),
                     w.winfo_ismapped(), w.winfo_y(), w.winfo_height()))
        except Exception as e:
            print("[L] %-22s ERR %s" % (label, e))

    dump("window", app)
    dump("search_entry", app.search_entry)
    # 侧边栏容器 = search_entry 的父
    dump("sidebar_wrap", app.search_entry.master)
    dump("sidebar_about", app.search_entry.master.winfo_children()[-1])
    dump("toolbar card", app.btn_scan.master.master.master)
    dump("card_count", app.card_count)
    dump("progress", app.progress)
    dump("status bar area", app.progress.master.master)
    print("[L] search_entry fg =", app.search_entry.cget("fg_color"),
          "border =", app.search_entry.cget("border_width"))
    # 侧边栏子控件清单
    for i, c in enumerate(app.search_entry.master.winfo_children()):
        print("[L]   sidebar child %d: %s  %dx%d" %
              (i, c.__class__.__name__, c.winfo_width(), c.winfo_height()))
    app.after(200, app.destroy)


app.after(2000, report)
app.mainloop()
