# -*- coding: utf-8 -*-
"""隔离测量：滚动成本到底来自 canvas 移动、还是其它回调。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import CleanerApp
app = CleanerApp()

def t_scroll_units(n=60):
    cv = app.scroll._parent_canvas
    t0 = time.perf_counter()
    for i in range(n):
        cv.yview_moveto((i % 40)/40.0)
        app.update_idletasks()
    return (time.perf_counter()-t0)*1000

def t_idle(n=60):
    t0 = time.perf_counter()
    for i in range(n):
        app.update_idletasks()
    return (time.perf_counter()-t0)*1000

def run():
    print("[i] 扫描前: 60次 yview+update = %.1f ms ; 60次 纯update = %.1f ms"
          % (t_scroll_units(), t_idle()))
    app.start_scan()
    app.after(13000, p2)

def p2():
    print("[i] 扫描后: 60次 yview+update = %.1f ms ; 60次 纯update = %.1f ms"
          % (t_scroll_units(), t_idle()))
    cv = app.scroll._parent_canvas
    # 统计滚动区内的控件总数（决定 Tk 每帧要做多少几何计算）
    def count(w):
        n = 1
        for c in w.winfo_children():
            n += count(c)
        return n
    print("[i] 滚动区控件总数(含嵌套):", count(app.scroll))
    print("[i] 主窗口控件总数:", count(app))
    # 单独测 configure 一次的成本（悬停动画每帧都调用）
    card = app.row_widgets[0]["card"]
    t0=time.perf_counter()
    for _ in range(20):
        card.configure(fg_color="#283250")
        app.update_idletasks()
    print("[i] 20次 card.configure(fg_color) = %.1f ms (单次 %.2f ms)"
          % ((time.perf_counter()-t0)*1000, (time.perf_counter()-t0)*1000/20))
    app.after(200, app.destroy)

app.after(1000, run)
app.mainloop()
