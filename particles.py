# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · 动画粒子背景（高性能 Canvas 渲染内核）。"""
import ctypes
import math
import random
import sys
import time
import weakref
from ctypes import wintypes
from collections import deque
import tkinter as tk
import customtkinter as ctk

import config
from config import PARTICLE_COLORS, MONO_FAMILY, _hex_rgb

_bg_registry = weakref.WeakValueDictionary()

# ============================================================
#  动画粒子背景层（v2.3.0 新增，v2.5.0 高性能重构）
#  - Canvas 实现的垂直渐变 + 漂浮发光粒子
#  - 粒子用预创建 oval + coords 原地更新，避免每帧 delete/recreate 开销
#  - v2.5.0 性能优化（目标 165Hz 丝滑）：
#    * 显示器刷新率探测 + perf_counter 精确帧节拍（绝对相位无累积漂移），
#      移除 v2.3.0 的 30fps 固定上限
#    * dt 时间基准物理：速度以 px/s 计，帧率波动不影响动画速度
#    * 平行数组存储 + sin 查找表：消除逐帧字典分配与 math.sin 调用
#    * 量化脏重绘：仅当像素级位置/半径变化时才调用 canvas.coords，
#      高帧率下粒子每帧仅亚像素位移，可省 90%+ 的 Tk 脏区刷新
#    * 爆发粒子对象池：复用 oval item，消除每帧 create/delete 抖动
#    * winfo_viewable 节流（0.5s 一次 Tcl 查询）+ 窗口不可见时降频省 CPU
#    * 自适应画质看门狗：帧耗时持续超预算自动减粒子、有裕量恢复，
#      低配机器自动降质保帧率，不掉帧
#    * 内置 FPS 表（EMA），--perf 参数可叠加显示 FPS/帧耗时/粒子数
# ============================================================
def _detect_refresh_rate():
    """探测主显示器刷新率（Hz）；失败回退 60。

    注：Python 3.13 的 ctypes.wintypes 不再导出 DEVMODEW/DISPLAY_DEVICEW 等结构体，
    故手工定义（与官方 DEVMODEW 字段顺序一致）。这避免了之前探测静默失败导致永远
    回退到 60 的问题。
    """
    try:
        if sys.platform != "win32":
            return 60
        class _DEVMODEW(ctypes.Structure):
            _fields_ = [
                ("dmDeviceName", ctypes.c_wchar * 32),
                ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD),
                ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD),
                ("dmFields", wintypes.DWORD),
                ("dmPosition", ctypes.c_long * 2),
                ("dmDisplayOrientation", wintypes.DWORD),
                ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", ctypes.c_short),
                ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short),
                ("dmFormName", ctypes.c_wchar * 32),
                ("dmLogPixels", wintypes.WORD),
                ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD),
                ("dmPelsHeight", wintypes.DWORD),
                ("dmDisplayFlags", wintypes.DWORD),
                ("dmDisplayFrequency", wintypes.DWORD),
                ("dmICMMethod", wintypes.DWORD),
                ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD),
                ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD),
                ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD),
                ("dmPanningHeight", wintypes.DWORD),
            ]
        dm = _DEVMODEW()
        dm.dmSize = ctypes.sizeof(_DEVMODEW)
        if ctypes.windll.user32.EnumDisplaySettingsW(None, 0, ctypes.byref(dm)):
            freq = int(dm.dmDisplayFrequency or 0)
            if 30 <= freq <= 1000:
                return freq
    except Exception:
        pass
    return 60


# 高精度定时器引用计数：Windows 默认定时器分辨率 15.6ms，`after()` 无法稳定到
# 6.06ms（165Hz）。timeBeginPeriod(1) 提升到 1ms（进程级生效，多实例引用计数）。
_timer_res_count = 0


def _timer_begin():
    global _timer_res_count
    if sys.platform != "win32":
        return
    _timer_res_count += 1
    if _timer_res_count == 1:
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass


def _timer_end():
    global _timer_res_count
    if sys.platform != "win32" or _timer_res_count <= 0:
        return
    _timer_res_count -= 1
    if _timer_res_count == 0:
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass


class AnimatedBackground:
    GRAD_BANDS = 48               # 渐变条带数（一次绘制，resize 时重绘）
    DEFAULT_PARTICLES = 46        # 主窗口粒子数
    DIALOG_PARTICLES = 22         # 对话框粒子数
    MIN_PARTICLES = 12            # 自适应降质下限（主窗口）
    MIN_DIALOG_PARTICLES = 8      # 自适应降质下限（对话框）
    MAX_FPS = 165                 # 目标帧率上限（按显示器刷新率适配，最高 165Hz）
    MIN_FPS = 30
    ADAPT_EVERY = 60              # 每 N 帧做一次自适应画质决策
    ADAPT_DOWN_RATIO = 1.30       # 帧耗时 > 1.30×预算 → 降 20% 粒子
    ADAPT_UP_RATIO = 0.60         # 帧耗时 < 0.60×预算 → 尝试恢复粒子
    VIEWABLE_CHECK_MS = 200       # winfo_viewable 轮询间隔（与隐藏节拍一致，恢复即满帧）
    HIDDEN_FRAME_MS = 200         # 窗口不可见时的调度间隔（5fps 省 CPU）
    SCROLL_TICK_MS = 33           # 滚动期间调度间隔（~30fps tick，仅统计不渲染）
    BURST_POOL = 96               # 爆发粒子 canvas item 对象池上限
    _SIN_BITS = 10                # sin 查找表 1024 项
    _SIN_SIZE = 1 << _SIN_BITS
    _SIN_MASK = _SIN_SIZE - 1
    _SIN_SCALE = _SIN_SIZE / (2 * math.pi)

    # 可被外部覆盖（CleanerApp 根据 CLI 参数设置）；None = 自动探测显示器
    TARGET_FPS = None
    PERF_MODE = False             # --perf：显示 FPS 叠加层

    def __init__(self, parent, particle_count=None, width=1120, height=800,
                 perf_label=None):
        self.parent = parent
        self.w = width
        self.h = height
        self._orig_count = particle_count or self.DEFAULT_PARTICLES
        self.particle_count = self._orig_count
        self._min_particles = (self.MIN_DIALOG_PARTICLES
                               if particle_count and particle_count <= self.DIALOG_PARTICLES
                               else self.MIN_PARTICLES)
        self.canvas = tk.Canvas(parent, highlightthickness=0, bd=0,
                                bg=config.C_BG, width=width, height=height)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        # 渐变三段：顶 -> 中 -> 底
        self.grad_stops = [
            (0.0, _hex_rgb(config.C_BG_TOP)),
            (0.5, _hex_rgb(config.C_BG_MID)),
            (1.0, _hex_rgb(config.C_BG_BOT)),
        ]
        # --- v2.5.0：平行数组存储（替代逐帧字典访问）---
        self._xs, self._ys = [], []
        self._vxs, self._vys = [], []
        self._rs, self._bases = [], []
        self._phases, self._pseeds = [], []
        self._hues = []
        self._glow_items, self._core_items = [], []
        self._last = []            # 上次绘制量化值 (ix, iy, rq)，脏重绘判断
        self._sin_lut = [math.sin(i * 2 * math.pi / self._SIN_SIZE)
                         for i in range(self._SIN_SIZE)]
        self._bursts = []          # 活动爆发粒子
        self._burst_free = []      # 爆发粒子 canvas item 对象池（空闲）
        self._grad_dirty = True
        self._running = True
        self._viewable = True
        self._viewable_check_t = -10.0    # 首次 _animate 立即做可见性检查
        self._scroll_until = 0.0         # 时间戳：滚动期持续到此时间
        # --- 帧率表（EMA，--perf 叠加层与 perf_test.py 验证用）---
        self._perf = time.perf_counter
        self._prev_t = self._perf()
        self._frame_count = 0
        self._fps_window_t = self._perf()
        self.fps = 0.0             # 当前实测 FPS（EMA）
        self._ema_ms = 0.0         # 帧耗时 EMA（ms）
        self.frame_ms = 0.0
        self._late_frames = 0      # 超预算追帧次数
        self._dt_hist = deque(maxlen=2400)  # 近帧耗时样本（性能验证用）
        self._target_fps = self._resolve_target_fps()
        self._frame_budget = 1.0 / self._target_fps
        # --- 可选 FPS 叠加层（--perf）---
        self._perf_label = None
        if self.PERF_MODE and perf_label is not False:
            self._build_perf_label()
        self._init_particles()
        parent.bind("<Configure>", self._on_resize, add="+")
        # 注册到全局表，滚动事件可按 toplevel 路由到此 bg
        try:
            _bg_registry[id(parent.winfo_toplevel())] = self
        except Exception:
            pass
        _timer_begin()
        self._animate()

    def set_scroll_activity(self):
        """标记滚动活跃期（250ms 内）。期间背景动画完全暂停渲染，把主循环让给滚动。"""
        self._scroll_until = self._perf() + 0.25

    # ---------- 目标帧率 ----------
    @classmethod
    def _resolve_target_fps(cls):
        fps = cls.TARGET_FPS or _detect_refresh_rate()
        if not fps or fps < cls.MIN_FPS:
            fps = cls.MIN_FPS
        return min(fps, cls.MAX_FPS)

    def _build_perf_label(self):
        try:
            lbl = ctk.CTkLabel(
                self.parent, text="-- FPS", font=(MONO_FAMILY, 10),
                text_color=config.C_SUCCESS, fg_color=config.C_GLASS_2, corner_radius=6,
                padx=8, pady=2
            )
            lbl.place(relx=1.0, x=-12, y=10, anchor="ne")
            self._perf_label = lbl
        except Exception:
            self._perf_label = None

    # ---------- 初始化 ----------
    def _init_particles(self):
        n = self.particle_count
        for _ in range(n):
            self._add_particle(y_rand=True)

    def _add_particle(self, y_rand=False):
        """追加一个粒子（含 canvas item），自适应恢复画质时复用。"""
        hue = random.choice(PARTICLE_COLORS)
        self._xs.append(random.uniform(0, self.w))
        self._ys.append(random.uniform(0, self.h) if y_rand else self.h + 12.0)
        # v2.5.0：速度改为 px/s（原 px/frame@30fps × 30），帧率无关
        self._vxs.append(random.uniform(-0.14, 0.14) * 30.0)
        self._vys.append(random.uniform(-0.42, -0.10) * 30.0)
        self._rs.append(random.uniform(0.9, 2.8))
        self._bases.append(random.uniform(0.55, 1.0))
        self._phases.append(random.uniform(0, 6.283))
        self._pseeds.append(random.uniform(0.04, 0.075) * 30.0)   # rad/s
        self._hues.append(hue)
        glow = self.canvas.create_oval(0, 0, 0, 0, outline=hue, width=1)
        core = self.canvas.create_oval(0, 0, 0, 0, fill=hue, outline="")
        self._glow_items.append(glow)
        self._core_items.append(core)
        self._last.append(None)    # None → 首帧强制绘制

    def _resize_particles(self, new_count):
        """自适应画质：增减粒子（并行数组与 canvas item 保持一致）。"""
        new_count = max(self._min_particles,
                        min(self._orig_count, int(new_count)))
        n = len(self._xs)
        if new_count > n:
            for _ in range(new_count - n):
                self._add_particle()
        elif new_count < n:
            canvas = self.canvas
            for i in range(n - 1, new_count - 1, -1):
                canvas.delete(self._glow_items[i])
                canvas.delete(self._core_items[i])
            del self._xs[new_count:], self._ys[new_count:]
            del self._vxs[new_count:], self._vys[new_count:]
            del self._rs[new_count:], self._bases[new_count:]
            del self._phases[new_count:], self._pseeds[new_count:]
            del self._hues[new_count:]
            del self._glow_items[new_count:], self._core_items[new_count:]
            del self._last[new_count:]
        self.particle_count = len(self._xs)

    # ---------- 渐变 ----------
    def _grad_color(self, t):
        stops = self.grad_stops
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0
                return (int(c0[0] + (c1[0] - c0[0]) * f),
                        int(c0[1] + (c1[1] - c0[1]) * f),
                        int(c0[2] + (c1[2] - c0[2]) * f))
        return stops[-1][1]

    def _draw_gradient(self):
        self.canvas.delete("grad")
        bands = self.GRAD_BANDS
        for i in range(bands):
            t0 = i / bands
            t1 = (i + 1) / bands
            c = self._grad_color((t0 + t1) / 2)
            y0 = t0 * self.h
            y1 = t1 * self.h + 1
            self.canvas.create_rectangle(
                0, y0, self.w, y1,
                fill="#%02x%02x%02x" % c, outline="", tags="grad"
            )
        # 渐变在最底层
        self.canvas.tag_lower("grad")

    # ---------- 粒子爆发（交互反馈） ----------
    def burst(self, x, y, color=None, count=22):
        color = color or config.C_PRIMARY_GLOW
        canvas = self.canvas
        free = self._burst_free
        for _ in range(count):
            ang = random.uniform(0, 6.283)
            spd = random.uniform(1.6, 5.2) * 30.0            # px/s
            if free:
                item = free.pop()
                canvas.itemconfigure(item, fill=color)
            else:
                item = canvas.create_oval(0, 0, 0, 0, fill=color,
                                          outline="", tags="burst")
            self._bursts.append({
                "x": x, "y": y,
                "vx": math.cos(ang) * spd,
                "vy": math.sin(ang) * spd - 36.0,            # 上抛 -1.2px/f@30fps
                "r": random.uniform(1.4, 3.4),
                "life": 1.0,
                "decay": random.uniform(0.022, 0.05) * 30.0,  # /s
                "item": item,
            })

    # ---------- 渲染热循环 ----------
    def _update_particles(self, dt):
        """平行数组 + sin 查找表 + 量化脏重绘（唯一的热循环）。"""
        xs, ys = self._xs, self._ys
        vxs, vys = self._vxs, self._vys
        rs, bases = self._rs, self._bases
        phases, pseeds = self._phases, self._pseeds
        last = self._last
        glows, cores = self._glow_items, self._core_items
        coords = self.canvas.coords
        lut = self._sin_lut
        sin_scale = self._SIN_SCALE
        mask = self._SIN_MASK
        w, h = self.w, self.h
        n = len(xs)
        for i in range(n):
            x = xs[i] + vxs[i] * dt
            y = ys[i] + vys[i] * dt
            ph = phases[i] + pseeds[i] * dt
            xs[i] = x
            ys[i] = y
            phases[i] = ph
            if y < -12:
                y = h + 12.0
                x = random.uniform(0, w)
                xs[i] = x
                ys[i] = y
            elif x < -12:
                x = w + 12.0
                xs[i] = x
            elif x > w + 12.0:
                x = -12.0
                xs[i] = x
            r = rs[i] * bases[i] * (0.65 + 0.35 * lut[int(ph * sin_scale) & mask])
            if r < 0.3:
                r = 0.3
            # 量化：位置 1px / 半径 0.25px。高帧率下粒子每帧仅亚像素位移，
            # 多数粒子无需每帧调用 canvas.coords → Tk 脏区大幅缩小
            ix = int(x)
            iy = int(y)
            rq = int(r * 4.0)
            prev = last[i]
            if prev is None or ix != prev[0] or iy != prev[1] or rq != prev[2]:
                last[i] = (ix, iy, rq)
                rr = rq * 0.25
                g = rr * 2.6
                coords(glows[i], ix - g, iy - g, ix + g, iy + g)
                coords(cores[i], ix - rr, iy - rr, ix + rr, iy + rr)

    def _update_bursts(self, dt):
        if not self._bursts:
            return
        canvas = self.canvas
        coords = canvas.coords
        alive = []
        free = self._burst_free
        for b in self._bursts:
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["vy"] += 2.7 * dt                # 重力 0.09px/f@30fps → 2.7px/s²
            b["life"] -= b["decay"] * dt
            if b["life"] > 0:
                r = max(0.5, b["r"] * b["life"])
                coords(b["item"], b["x"] - r, b["y"] - r, b["x"] + r, b["y"] + r)
                alive.append(b)
            else:
                coords(b["item"], -100, -100, -100, -100)   # 移出屏幕待复用
                free.append(b["item"])
        self._bursts = alive
        if alive:
            canvas.tag_raise("burst")
        # 对象池上限保护：清理多余空闲 item
        if len(free) > self.BURST_POOL:
            for _ in range(len(free) - self.BURST_POOL):
                canvas.delete(free.pop())

    # ---------- 调度 ----------
    def _on_resize(self, _e):
        try:
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()
        except Exception:
            return
        if w > 10 and h > 10:
            self.w, self.h = w, h
            self._grad_dirty = True

    def stop(self):
        self._running = False
        try:
            _bg_registry.pop(id(self.parent.winfo_toplevel()), None)
        except Exception:
            pass
        _timer_end()
        if self._perf_label is not None:
            try:
                self._perf_label.destroy()
            except Exception:
                pass
            self._perf_label = None

    def _adapt_quality(self):
        """自适应画质看门狗：持续超帧预算 → 降 20% 粒子；持续有裕量 → 恢复。"""
        budget = self._frame_budget * 1000.0
        ema = self._ema_ms
        if ema <= 0:
            return
        if ema > budget * self.ADAPT_DOWN_RATIO and self.particle_count > self._min_particles:
            self._resize_particles(int(self.particle_count * 0.8))
        elif (ema < budget * self.ADAPT_UP_RATIO
                and self.particle_count < self._orig_count):
            self._resize_particles(self.particle_count + 4)

    def _animate(self):
        if not self._running:
            return
        now = self._perf()
        dt = now - self._prev_t
        self._prev_t = now
        if dt <= 0:
            dt = 1e-6
        elif dt > 0.25:                # 挂起/切屏后的巨大 dt 钳制，防止跳变
            dt = 0.25
        # winfo_viewable 节流：Tcl 往返从每帧降到 5 次/秒
        if now - self._viewable_check_t > self.VIEWABLE_CHECK_MS / 1000.0:
            try:
                self._viewable = bool(self.parent.winfo_viewable())
            except Exception:
                self._viewable = True
            self._viewable_check_t = now
        if self._viewable:
            if self._grad_dirty:
                self._draw_gradient()
                self._grad_dirty = False
            # 滚动期间完全暂停粒子渲染（背景"冻结"），主循环全速服务滚动事件，
            # 消除快速滑动时背景重绘与滚动重绘争用的割裂感
            scrolling = now < self._scroll_until
            if not scrolling:
                if self._frame_count % self.ADAPT_EVERY == 0:
                    self._adapt_quality()
                self._update_particles(dt)
                self._update_bursts(dt)
        # ---- 帧率统计（EMA）----
        self._frame_count += 1
        frame_ms = dt * 1000.0
        self._ema_ms = self._ema_ms * 0.9 + frame_ms * 0.1
        self.frame_ms = self._ema_ms
        self._dt_hist.append(frame_ms)
        if self._frame_count % 30 == 0:
            now2 = self._perf()
            fps = 30.0 / (now2 - self._fps_window_t)
            self._fps_window_t = now2
            self.fps = self.fps * 0.8 + fps * 0.2
        # ---- 叠加层刷新（约每 0.4s）----
        if self._perf_label is not None and self._frame_count % 66 == 0:
            try:
                self._perf_label.configure(
                    text=f"{self.fps:5.0f} FPS  {self._ema_ms:4.1f}ms  {self.particle_count}粒"
                )
            except Exception:
                pass
        # ---- 帧节拍调度：对齐帧预算，绝对相位自修正，无累积漂移 ----
        if self._viewable and not (now < self._scroll_until):
            elapsed = self._perf() - now
            remain_ms = self._frame_budget * 1000.0 - elapsed * 1000.0
            if remain_ms < 1.0:
                self._late_frames += 1
                delay = 1            # 已超预算：追帧，等看门狗降质
            else:
                delay = int(remain_ms)
            delay = max(1, delay)
        else:
            delay = self.SCROLL_TICK_MS if now < self._scroll_until else self.HIDDEN_FRAME_MS
        self.parent.after(delay, self._animate)
