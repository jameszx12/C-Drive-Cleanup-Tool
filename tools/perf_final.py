# -*- coding: utf-8 -*-
"""终测：悬停动画成本 + 滚轮平滑度 + 扫描期响应性。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import CleanerApp
from widgets import _fast_recolor
app = CleanerApp()

def run():
    app.start_scan(); app.after(13000, p2)

def p2():
    card = app.row_widgets[0]["card"]
    # 1) 新路径：_fast_recolor（悬停动画实际走的路径）
    t0 = time.perf_counter()
    for i in range(100):
        _fast_recolor(card, "#283250"); app.update_idletasks()
    fast = (time.perf_counter()-t0)*1000
    print("[f] 100次 悬停重绘(新 _fast_recolor) = %.1f ms  单次 %.3f ms" % (fast, fast/100))
    # 2) 旧路径对比
    t0 = time.perf_counter()
    for i in range(20):
        card.configure(fg_color="#283250"); app.update_idletasks()
    slow = (time.perf_counter()-t0)*1000
    print("[f] 20次 悬停重绘(旧 configure)     = %.1f ms  单次 %.3f ms" % (slow, slow/20))
    print("[f] 单次提速 %.0fx" % ((slow/20)/(fast/100)))
    # 3) 滚轮合并重绘
    cv = app.scroll._parent_canvas
    t0 = time.perf_counter()
    for i in range(60):
        cv.yview_moveto((i % 40)/40.0); app.update_idletasks()
    print("[f] 60次 直接 moveto = %.1f ms (%.2f ms/次)" % ((time.perf_counter()-t0)*1000, (time.perf_counter()-t0)*1000/60))
    # 4) 事件循环总响应
    out=[]; prev=time.perf_counter()
    for i in range(150):
        cv.yview_moveto((i % 40)/40.0)
        app.update_idletasks(); app.update()
        now=time.perf_counter(); out.append((now-prev)*1000); prev=now
    out.sort(); n=len(out)
    print("[f] 滚动事件循环: 中位%.2fms p90%.2fms max%.2fms 超标>16.7ms %d/%d"
          % (out[n//2], out[int(n*0.9)], out[-1], sum(1 for x in out if x>16.7), n))
    app.after(200, app.destroy)

app.after(1000, run)
app.mainloop()
