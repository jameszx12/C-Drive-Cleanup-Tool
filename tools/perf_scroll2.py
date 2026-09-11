# -*- coding: utf-8 -*-
"""滚动开销拆解 v2：区分 moveto 本身 / 内部布局重算 / 每卡额外成本。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import CleanerApp
import tkinter as tk
app = CleanerApp()

def count_w(w):
    n = 1
    for c in w.winfo_children():
        n += count_w(c)
    return n

def bench(fn, n=60, warm=8):
    for _ in range(warm):
        fn(); app.update_idletasks()
    t0 = time.perf_counter()
    for i in range(n):
        fn(i); app.update_idletasks()
    return (time.perf_counter() - t0) * 1000 / n

def run():
    app.start_scan(); app.after(13000, p2)

def p2():
    cv = app.scroll._parent_canvas
    lc = app.list_container
    print("[p2] 卡片数 =", len(app.row_widgets))
    print("[p2] list_container 子树控件数 =", count_w(lc))

    ncards = max(1, len(app.row_widgets))

    # A) 纯 moveto（真实滚动）
    a = bench(lambda i: cv.yview_moveto((i % 40) / 40.0))
    # B) 同一位置反复 moveto（无位移，隔离"位移导致的布局"成本）
    b = bench(lambda i: cv.yview_moveto(0.5))
    # C) 只 update_idletasks，不动 canvas
    c = bench(lambda i: None)
    # D) moveto + 完整 update（含绘制）
    def d(i):
        cv.yview_moveto((i % 40) / 40.0); app.update()
    t0 = time.perf_counter()
    for i in range(60):
        d(i)
    dd = (time.perf_counter() - t0) * 1000 / 60

    print("[p2] A 真实位移 moveto+idle   = %.2f ms/次" % a)
    print("[p2] B 同位 moveto+idle       = %.2f ms/次" % b)
    print("[p2] C 仅 idle 基线           = %.2f ms/次" % c)
    print("[p2] D moveto + 完整 update   = %.2f ms/次" % dd)
    print("[p2] -> 位移净成本 A-C = %.2f ms   单卡摊销 = %.3f ms"
          % (a - c, (a - c) / ncards))

    # E) 单卡 configure 成本（验证级联是否仍是瓶颈）
    card = app.row_widgets[0]["card"]
    e = bench(lambda i: card.configure(fg_color=("#283250" if i % 2 else "#1d2438")))
    print("[p2] E 单卡 configure fg_color = %.2f ms/次" % e)

    app.after(200, app.destroy)

app.after(1000, run)
app.mainloop()
