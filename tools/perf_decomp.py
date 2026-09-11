# -*- coding: utf-8 -*-
"""拆解滚动成本：Tk 几何计算 vs Python 回调。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import CleanerApp
app = CleanerApp()
cv = app.scroll._parent_canvas

def t(label, fn, n):
    t0 = time.perf_counter()
    for i in range(n): fn(i)
    print("[d] %-34s %7.1f ms  (%.2f ms/次)" % (label, (time.perf_counter()-t0)*1000, (time.perf_counter()-t0)*1000/n))

def run():
    app.start_scan(); app.after(13000, p2)

def p2():
    n = 40
    t("yview_moveto + update_idletasks", lambda i: (cv.yview_moveto((i%40)/40.0), app.update_idletasks()), n)
    t("yview_moveto 不动(相同值)", lambda i: (cv.yview_moveto(0.5), app.update_idletasks()), n)
    t("canvas.xview() 只读", lambda i: (cv.yview(), app.update_idletasks()), n)
    t("滚动区 bbox('all')", lambda i: (cv.bbox("all"), app.update_idletasks()), n)
    t("winfo_children 遍历卡片", lambda i: ([w.winfo_children() for w in [it["card"] for it in app.row_widgets[:3]]], app.update_idletasks()), n)
    # 逐个卡片测量：滚动时每张卡片要重算多少
    print("[d] 卡片数:", len(app.row_widgets), " 滚动区控件: 677")
    print("[d] 每卡平均子控件:", 677 // max(1, len(app.row_widgets)))
    app.after(200, app.destroy)

app.after(1000, run)
app.mainloop()
