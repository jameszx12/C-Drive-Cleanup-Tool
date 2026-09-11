# -*- coding: utf-8 -*-
"""性能基准：测量粒子动画实际帧率与帧耗时分布（目标 165Hz 稳定不掉帧）。

用法（本机需有 tkinter，建议 D:\\miniconda3\\python.exe 运行）：
    python perf_test.py              # 裸 Canvas 模式（默认 1120x800 / 46 粒子）
    python perf_test.py --full       # 完整主窗口模式（CleanerApp 实测）
    python perf_test.py --fps 165    # 覆盖目标帧率
    python perf_test.py --secs 8     # 测量时长（预热 3s 不计入）
    python perf_test.py --particles 60 --size 1920x1080

运行期间会短暂弹出测试窗口（约 11s），结束后自动关闭并打印报告。
"""
import sys
import os
import time
import statistics
import tkinter as tk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as M


def _parse_size(s):
    w, _, h = s.lower().partition("x")
    return (int(w or 1120), int(h or 800))


def _run_sampling(root, bg, secs):
    """驱动主循环并采样：返回 (帧数增量, 追帧次数增量)。"""
    n0, late0 = bg._frame_count, bg._late_frames
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < secs:
        root.update()
        time.sleep(0.001)
    return bg._frame_count - n0, bg._late_frames - late0


def _report(mode, bg, secs, n, late):
    hist = list(bg._dt_hist)
    hist.sort()
    def pct(p):
        return hist[min(len(hist) - 1, int(len(hist) * p))] if hist else 0.0
    avg_fps = n / secs
    print("=" * 62)
    print("  性能基准报告  |  模式:", mode)
    print("-" * 62)
    print(f"  目标帧率      : {bg._target_fps} Hz  (帧预算 {bg._frame_budget*1000:.2f} ms)")
    print(f"  实测平均帧率  : {avg_fps:.1f} FPS  ({n} 帧 / {secs:.1f}s)")
    if hist:
        print(f"  帧耗时分布    : p50 {pct(0.50):.2f}ms  p95 {pct(0.95):.2f}ms  "
              f"p99 {pct(0.99):.2f}ms  max {hist[-1]:.2f}ms")
        worst_fps = 1000.0 / hist[-1]
        print(f"  最差瞬时帧率  : {worst_fps:.0f} FPS")
    print(f"  超预算追帧    : {late} 次")
    print(f"  当前粒子数    : {bg.particle_count}  (EMA 帧耗时 {bg._ema_ms:.2f}ms)")
    # 达标判定：平均帧率 >= 目标 95%，且 p99 帧耗时 < 1.5×预算
    ok_fps = avg_fps >= bg._target_fps * 0.95
    ok_p99 = (pct(0.99) if hist else 9e9) < bg._frame_budget * 1000.0 * 1.5
    verdict = "PASS ✔" if (ok_fps and ok_p99) else "FAIL ✘"
    print("-" * 62)
    print(f"  结论          : {verdict}  "
          f"({'帧率达标' if ok_fps else '帧率不足'} + "
          f"{'帧耗时稳定' if ok_p99 else '帧耗时抖动'})")
    print("=" * 62)
    return ok_fps and ok_p99


def main():
    args = sys.argv[1:]
    full = "--full" in args
    fps_target = None
    secs = 8.0
    warmup = 3.0
    particles = None
    size = (1120, 800)
    for i, a in enumerate(args):
        if a == "--fps" and i + 1 < len(args):
            fps_target = int(args[i + 1])
        elif a == "--secs" and i + 1 < len(args):
            secs = float(args[i + 1])
        elif a == "--particles" and i + 1 < len(args):
            particles = int(args[i + 1])
        elif a == "--size" and i + 1 < len(args):
            size = _parse_size(args[i + 1])

    if fps_target:
        M.AnimatedBackground.TARGET_FPS = fps_target
    M.AnimatedBackground.PERF_MODE = False

    if full:
        app = M.CleanerApp()
        app.update()
        bg = app.bg
        mode = "完整主窗口 (CleanerApp)"
    else:
        root = tk.Tk()
        root.geometry(f"{size[0]}x{size[1]}")
        bg = M.AnimatedBackground(root, particle_count=particles, width=size[0],
                                  height=size[1], perf_label=False)
        app = root
        mode = f"裸 Canvas ({size[0]}x{size[1]}, {bg.particle_count} 粒子)"

    # 预热（跳过初始渐变绘制与计时器抖动）
    _run_sampling(app, bg, warmup)
    bg._dt_hist.clear()
    n, late = _run_sampling(app, bg, secs)
    ok = _report(mode, bg, secs, n, late)

    if full:
        app._on_close()
    else:
        root.destroy()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
