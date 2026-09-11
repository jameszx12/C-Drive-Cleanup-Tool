# -*- coding: utf-8 -*-
"""逐项排查滚动开销：分别测 空滚动区 / 有卡片 / 悬停动画进行中。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import CleanerApp
app = CleanerApp()

def measure(n=80, act=None):
    out = []
    prev = time.perf_counter()
    for i in range(n):
        if act: act(i)
        app.update_idletasks(); app.update()
        now = time.perf_counter(); out.append((now-prev)*1000); prev = now
    out.sort(); n2=len(out)
    return out[n2//2], out[int(n2*0.9)], out[-1], sum(1 for x in out if x>16.7), n2

def scroll(i):
    app.scroll._parent_canvas.yview_moveto((i % 40)/40.0)

def run():
    print("[p] 阶段A: 扫描前(空列表) 滚动")
    m = measure(80, scroll); print("[p]   中位%.2f p90%.2f max%.2f 超标%d/%d" % m)
    app.start_scan()
    app.after(13000, phase2)

def phase2():
    print("[p] 阶段B: 23张卡片 滚动")
    m = measure(80, scroll); print("[p]   中位%.2f p90%.2f max%.2f 超标%d/%d" % m)
    # 数卡片 canvas item 总数
    tot = 0
    for it in app.row_widgets:
        tot += len(it["card"]._canvas.find_all())
    print("[p]   卡片canvas item 合计:", tot, " 每卡平均:", tot//max(1,len(app.row_widgets)))
    # 单独测 canvas 坐标更新成本
    t0=time.perf_counter()
    for _ in range(50):
        app.scroll._parent_canvas.yview_moveto(0.5)
        app.update_idletasks()
    print("[p]   50次 yview_moveto(纯滚动,无卡片区)耗时: %.1fms" % ((time.perf_counter()-t0)*1000))
    app.after(200, app.destroy)

app.after(1000, run)
app.mainloop()
