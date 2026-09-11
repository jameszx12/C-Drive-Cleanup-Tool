# -*- coding: utf-8 -*-
"""性能校验：模拟连续滚动 + 悬停，统计主线程事件处理耗时与帧间隔。"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import CleanerApp
app = CleanerApp()
stats = {"idle": [], "scroll": [], "hover": []}

def sample(tag, n, act=None):
    """测量 n 次事件循环迭代的间隔（越小越顺）。"""
    out = []
    prev = time.perf_counter()
    for i in range(n):
        if act:
            act(i)
        app.update_idletasks()
        app.update()
        now = time.perf_counter()
        out.append((now - prev) * 1000)
        prev = now
    stats[tag] = out

def run():
    # 1. 空闲基线（触发扫描让卡片存在，然后测空转）
    app.start_scan()
    app.after(13000, phase2)

def phase2():
    sample("idle", 120)
    # 2. 模拟滚动
    def do_scroll(i):
        inner = app.scroll._parent_canvas
        inner.yview_moveto((i % 40) / 40.0)
    sample("scroll", 120, do_scroll)
    # 3. 模拟悬停卡片
    cards = [it["card"] for it in app.row_widgets[:6]]
    def do_hover(i):
        c = cards[i % len(cards)] if cards else None
        if c is None: return
        try:
            c.event_generate("<Enter>") if i % 2 == 0 else c.event_generate("<Leave>")
        except Exception:
            pass
    sample("hover", 120, do_hover)

    def rep(tag):
        v = sorted(stats[tag])
        if not v: return
        n = len(v)
        print(f"[perf] {tag:7s} n={n:4d} 中位={v[n//2]:6.2f}ms p90={v[int(n*0.9)]:6.2f}ms "
              f"max={v[-1]:7.2f}ms  >16.7ms: {sum(1 for x in v if x>16.7)}/{n}")
    print("[perf] ---- 主线程事件循环间隔（越小越顺滑，16.7ms=60fps 预算）----")
    for t in ("idle", "scroll", "hover"):
        rep(t)
    app.after(200, app.destroy)

app.after(1000, run)
app.mainloop()
