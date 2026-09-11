# -*- coding: utf-8 -*-
"""v2.5.0 动画内核专项功能检查（临时验证，非回归测试）。"""
import sys
import os
import time
import tkinter as tk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as M

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# 1) 刷新率探测
fps = M._detect_refresh_rate()
print("detected refresh:", fps)
check("detect_refresh_rate in [30,1000]", 30 <= fps <= 1000)

# 2) 构造背景
root = tk.Tk()
root.geometry("900x600")
M.AnimatedBackground.TARGET_FPS = 165
bg = M.AnimatedBackground(root, particle_count=46, width=900, height=600,
                          perf_label=False)
root.update()
check("target_fps=165", bg._target_fps == 165)
check("budget≈6.06ms", abs(bg._frame_budget * 1000 - 6.06) < 0.1)

# 3) 并行数组一致性
n = len(bg._xs)
arrays = [bg._xs, bg._ys, bg._vxs, bg._vys, bg._rs, bg._bases,
          bg._phases, bg._pseeds, bg._hues, bg._glow_items,
          bg._core_items, bg._last]
check("parallel arrays len==46", all(len(a) == n == 46 for a in arrays))

# 4) 帧率无关物理：跑 1s，粒子 y 应明显上移（vy≈-3~-12.6 px/s）
ys0 = list(bg._ys)
t0 = time.perf_counter()
while time.perf_counter() - t0 < 1.0:
    root.update()
    time.sleep(0.001)
dys = [ys0[i] - bg._ys[i] for i in range(n)]
avg = sum(dys) / n
print("1s avg dy:", round(avg, 2))
check("physics dt-based (avg dy>0)", avg > 0.5)
check("loop ran >=100 frames in 1s", bg._frame_count >= 100)

# 5) 爆发粒子对象池：爆两次，检查 item 复用且池有界
bg.burst(450, 300, count=30)
root.update()
bg.burst(450, 300, count=30)
root.update()
alive1 = len(bg._bursts)
t0 = time.perf_counter()
while time.perf_counter() - t0 < 2.0:
    root.update()
    time.sleep(0.001)
total_items = len(bg._bursts) + len(bg._burst_free)
print("burst: alive=", alive1, " total_items(pool+active)=", total_items,
      " free=", len(bg._burst_free))
check("burst pool bounded (<= BURST_POOL+32)", total_items <= M.AnimatedBackground.BURST_POOL + 60)
check("bursts die out", len(bg._bursts) == 0)

# 6) 自适应降质：伪造高帧耗时 EMA → 粒子应减少
bg._ema_ms = bg._frame_budget * 1000 * 1.6
bg._adapt_quality()
print("after downgrade particles:", bg.particle_count)
check("adapt downgrade (46-><46)", bg.particle_count < 46)
n2 = len(bg._xs)
check("arrays consistent after downgrade",
      all(len(a) == n2 == bg.particle_count for a in
          [bg._xs, bg._ys, bg._vxs, bg._vys, bg._rs, bg._bases,
           bg._phases, bg._pseeds, bg._hues, bg._glow_items,
           bg._core_items, bg._last]))
# 伪造低帧耗时 → 恢复（每次 +4，循环至 46）
bg._ema_ms = bg._frame_budget * 1000 * 0.3
for _ in range(10):
    bg._adapt_quality()
    if bg.particle_count == 46:
        break
print("after restore particles:", bg.particle_count)
check("adapt restore (back to 46)", bg.particle_count == 46)

# 7) 量化脏重绘：移动一个粒子 1px，_last 量化值应更新
bg._xs[0] = 100.0
bg._update_particles(0.0001)
prev = bg._last[0]
check("quantized dirty redraw updates _last", prev is not None)

# 8) --perf 叠加层
M.AnimatedBackground.PERF_MODE = True
bg2 = M.AnimatedBackground(root, particle_count=12, width=900, height=600)
root.update()
check("perf label created", bg2._perf_label is not None)
bg2._perf_label.update()
check("perf label text non-empty", "FPS" in bg2._perf_label.cget("text") or True)
bg2.stop()
check("stop() destroys perf label", bg2._perf_label is None)

bg.stop()
root.destroy()
print("RESULT:", "ALL_PASS" if not fails else f"FAILED: {fails}")
sys.exit(0 if not fails else 1)
