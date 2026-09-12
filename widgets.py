# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · UI 组件库（v4.0 全新设计系统）。

设计原则
  1. **单一绘制源**：所有圆角/描边/高光一律画在控件自己的 canvas 内部，
     坐标严格内缩 >= 1px —— 彻底规避 customtkinter 的 font_shapes 圆角外溢。
  2. **直接改色，不 configure**：悬停/选中只 itemconfig canvas 上的图元，
     绕开 CTk 的子控件递归 configure（实测单片单帧 12ms → 0.2ms）。
  3. **层级靠明度，不靠边框**：面板色按 SURFACE → SURFACE_2 → SURFACE_3
     逐层提亮，描边只用于强调，视觉更干净现代。
  4. **动效克制**：帧数 <= 4、帧间隔 >= 18ms，绝不与滚动抢主线程。
"""
import os as _os
import tkinter as tk
import customtkinter as ctk

import config
import theme as T
from config import FONT_FAMILY, MONO_FAMILY, _hex_rgb
from icons import resource_dir

# =================================================================== 基础工具

def fnt(size, weight="normal", family=None):
    """统一字体工厂（family 默认中文字体）。"""
    return ctk.CTkFont(family=family or FONT_FAMILY, size=size, weight=weight)


def mono_fnt(size=11):
    return ctk.CTkFont(family=MONO_FAMILY, size=size)


def fmt_size(n):
    """人类可读的体积格式，自动选择最大合适单位并保留动态精度。"""
    try:
        n = float(n)
    except Exception:
        return "0 B"
    if n < 1024:
        return f"{int(n)} B"
    for unit, div, prec in (("TB", 1024 ** 4, 2), ("GB", 1024 ** 3, 2),
                            ("MB", 1024 ** 2, 1), ("KB", 1024, 1)):
        if n >= div:
            return f"{n / div:.{prec}f} {unit}"
    return "0 B"


def _mix_color(c1, c2, t):
    """按比例混合两色：t=0 全 c1，t=1 全 c2。用于生成淡色底/描边。"""
    try:
        r1, g1, b1 = _hex_rgb(c1)
        r2, g2, b2 = _hex_rgb(c2)
        return "#%02x%02x%02x" % (
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t))
    except Exception:
        return c1


def _luma(hexcolor):
    """感知亮度（0-255）。用于判断「深色还是浅色面板」以选高光方向。"""
    try:
        r, g, b = _hex_rgb(hexcolor)
        return (r * 299 + g * 587 + b * 114) / 1000
    except Exception:
        return 0.0


def _is_dark(hexcolor):
    return _luma(hexcolor) < 140


def rounded_poly(x0, y0, x1, y1, r):
    """生成圆角矩形顶点（配 smooth=True）。坐标可为浮点，用于精确内缩。"""
    r = max(0.0, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    return [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1,
        x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]


def rule_visual(rule):
    """清理类别的强调色 + 分类名。

    v4.0：强调色**跟随当前主题**取值 —— 深浅两套色板各有一组
    明度合适的强调色，直接用 DARK 的值会在浅色底上显得过饱和
    （表现为卡片/徽章周围一圈彩色光晕）。
    """
    pal = T.tokens(config.CURRENT_THEME)
    if rule.get("type") == "deep":
        return ("#8b5cf6" if config.CURRENT_THEME == "dark" else "#7c4ddb"), "深度扫描"
    if rule.get("type") == "update":
        return pal["INFO"], "更新安装包"
    cat = rule.get("cat")
    # 两类色值：dark 用高亮色（深底可读），light 用中深色（白底可读）
    if config.CURRENT_THEME == "dark":
        _COLORS = {
            "system": "#60a5fa", "browser": pal["SUCCESS"], "app": pal["WARN"],
            "dev": pal["INFO"], "game": "#a855f7", "media": "#f472b6",
            "cloud": "#22d3ee", "driver": "#94a3b8",
        }
    else:
        _COLORS = {
            "system": "#2563eb", "browser": pal["SUCCESS"], "app": pal["WARN"],
            "dev": pal["INFO"], "game": "#7c3aed", "media": "#db2777",
            "cloud": "#0891b2", "driver": "#64748b",
        }
    _NAMES = {
        "system": "系统垃圾", "browser": "浏览器", "app": "应用缓存",
        "dev": "开发工具", "game": "游戏平台", "media": "媒体工具",
        "cloud": "云盘", "driver": "驱动显卡",
    }
    if cat in _COLORS:
        return _COLORS[cat], _NAMES[cat]
    return pal["WARN"], "应用缓存"

# =================================================================== 图标

_icon_cache = {}


def ui_icon(name, size=20):
    """加载 UI 线性图标（按主题选明暗变体，模块级缓存防 GC）。缺失返回 None。"""
    variant = "d" if config.CURRENT_THEME == "dark" else "l"
    key = f"{variant}_{name}_{size}"
    if key in _icon_cache:
        return _icon_cache[key]
    try:
        src = min((20, 24), key=lambda s: abs(s - size))
        p = _os.path.join(resource_dir(), "ui", f"{variant}_{name}_{src}.png")
        if not _os.path.isfile(p):
            p = _os.path.join(resource_dir(), "ui", f"{variant}_{name}_20.png")
            if not _os.path.isfile(p):
                return None
        img = tk.PhotoImage(file=p)
        _icon_cache[key] = img
        return img
    except Exception:
        return None


def rule_icon_photo(rule_key, size=34):
    """清理项图标：从 icons/<key>.png 加载并缩放到 size。"""
    key = f"rule_{rule_key}_{size}"
    if key in _icon_cache:
        return _icon_cache[key]
    try:
        p = _os.path.join(resource_dir(), rule_key + ".png")
        if not _os.path.isfile(p):
            return None
        photo = tk.PhotoImage(file=p)
        if photo.width() > size:
            s = max(1, photo.width() // size)
            photo = photo.subsample(s, s)
        _icon_cache[key] = photo
        return photo
    except Exception:
        return None


# =================================================================== Tooltip

# 浮层窗口（Toast / Tooltip / 下拉框）魔术底色：无边框 tk.Toplevel 默认是浅色底，
# 里面圆角卡片盖不住窗口四角，会露出一圈白色方框。把窗口底设为几乎不用的近黑色
# 并设为透明色键，四角即透明，浮层真正"浮"起来（圆角外全透）。
TIP_MAGIC_BG = "#000001"


def style_popup(top):
    """无边框浮层去白边：魔术底色 + 透明色键（失败则至少保留近黑底）。"""
    try:
        top.configure(bg=TIP_MAGIC_BG)
    except Exception:
        pass
    try:
        top.attributes("-transparentcolor", TIP_MAGIC_BG)
    except Exception:
        pass


class Tooltip:
    """延迟悬浮提示气泡（描边式，非玻璃卡片，层级更轻）。

    v4.3.0：移除 _registry（只写不读，且强引用已销毁控件导致跨扫描/
    跨主题切换的内存泄漏）。Tooltip 生命周期跟随宿主控件即可。
    """

    DELAY = 420

    def __init__(self, widget, text, **kw):
        self.widget = widget
        self.text = text
        self._tip = None
        self._job = None
        for ev, fn in (("<Enter>", self._schedule), ("<Leave>", self._hide),
                       ("<ButtonPress>", self._hide)):
            try:
                widget.bind(ev, fn, add="+")
            except Exception:
                pass

    def _schedule(self, _e=None):
        self._cancel()
        try:
            self._job = self.widget.after(self.DELAY, self._show)
        except Exception:
            self._job = None

    def _show(self):
        try:
            x = self.widget.winfo_rootx() + 4
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.attributes("-topmost", True)
            style_popup(self._tip)
            box = ctk.CTkFrame(self._tip, fg_color=config.C_GLASS_3,
                               corner_radius=T.R.SM, border_width=0)
            box.pack()
            ctk.CTkLabel(box, text=self.text, font=fnt(T.FS.CAPTION),
                         text_color=config.C_TEXT, padx=10, pady=6).pack()
            self._tip.wm_geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _hide(self, _e=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

# =================================================================== 卡片基元

def _fast_recolor(widget, color):
    """直接改 canvas 上 inner_parts 的填充色，跳过 CTk 的 configure 级联。

    CTkFrame.configure(fg_color=...) 会遍历全部子控件逐个 configure(bg_color=)，
    单张卡片（约 30 个子控件）实测 ~12ms；本函数只改一个图元，实测 ~0.2ms。
    """
    try:
        c = widget._apply_appearance_mode(color)
        cv = widget._canvas
        cv.itemconfig("inner_parts", fill=c, outline=c)
        return True
    except Exception:
        return False


def draw_card_shell(card, *, fg=None, radius=T.R.LG, border=None,
                    hl=True, hl_strength=0.07, shadow=True):
    """在卡片 canvas 内部绘制：内缩描边 + 顶部高光 + 底部阴影带。

    v4.0 关键约束（面板边缘不再外溢）：
      Tk canvas 的 ``smooth=True`` 多边形走的是贝塞尔插值，顶点在 1.0 附近时
      曲线会向上/向外凸出到 0.5 甚至越出控件边界；``width=1`` 的描边又会以
      线条为中心向两侧各溢出 0.5px。顶部高光线画在 y=1.5 同样会凸到 y=0.5。
      这些亚像素外溢在深色底上就是一圈可见的淡紫/淡蓝「彩色边缘」。
      因此本实现统一内缩到 **>= 2.0**（描边 2.0、高光 3.0、阴影 h-3.0），
      并去掉描边线宽的一半外扩风险，确保任何情况下都不越界。

    同时必须等控件**真正映射**后再绘制：未完成布局时 winfo_width() 返回 1，
    会画出一条退化的细线（表现为窗口上横贯的亮线）。

    返回绘制函数（便于尺寸变化后重绘）。
    """
    fg = config.C_GLASS if fg is None else fg
    border = config.C_GLASS_BORDER if border is None else border

    # 统一的安全内缩量：>= 2.0 才能吸收 smooth 曲线与线宽的外扩
    INSET = 2.0

    def draw():
        try:
            if not card.winfo_exists() or not card.winfo_ismapped():
                return
            w, h = card.winfo_width(), card.winfo_height()
            if w <= 30 or h <= 20:
                return      # 尚未完成布局，避免画出退化细线
            cv = card._canvas
            cv.delete("shell")
            r = max(2, min(int(radius), w // 2 - 4, h // 2 - 4))
            dark = _is_dark(fg)

            # 内缩描边：坐标严格 >= 2.0，smooth 曲线不会凸出到边界外
            if border:
                cv.create_polygon(
                    rounded_poly(INSET, INSET, w - INSET, h - INSET, r),
                    smooth=True, fill="", outline=border, width=1,
                    tags=("shell", "card_border"))

            side = max(6, r + 4)
            if hl and w - 2 * side > 10:
                # 顶部高光线：下移到 y=3.0，远离上边界
                hc = (_mix_color(fg, "#ffffff", hl_strength) if dark
                      else _mix_color(fg, border, 0.30))
                cv.create_line(side, 3.0, w - side, 3.0,
                               fill=hc, width=1, tags=("shell",))
            if shadow and w - 2 * side > 10:
                # 底部阴影线：上移到 h-3.0，远离下边界
                sc = _mix_color(fg, "#000000", 0.10 if dark else 0.04)
                cv.create_line(side, h - 3.0, w - side, h - 3.0,
                               fill=sc, width=1, tags=("shell",))
        except Exception:
            pass

    _schedule_shell_draw(card, draw)
    return draw


def _schedule_shell_draw(card, draw):
    """延迟 + 尺寸变化时重绘描边（保证在布局完成后才绘制）。"""
    def once():
        draw()
    try:
        card.after(50, once)
    except Exception:
        pass
    # 首次映射 / 尺寸变化时再画一次（after 可能早于布局完成）
    state = {"n": 0}

    def on_conf(_e=None):
        if state["n"] >= 3:
            return
        state["n"] += 1
        draw()

    try:
        card.bind("<Configure>", on_conf, add="+")
    except Exception:
        pass


def make_card(parent, *, fg=None, radius=T.R.LG, height=None, border=None,
              border_width=0):
    """统一样式的面板/卡片容器（无 CTk 边框，描边自绘内缩）。"""
    fg = config.C_GLASS if fg is None else fg
    border = config.C_GLASS_BORDER if border is None else border
    kw = dict(fg_color=fg, corner_radius=radius, border_width=border_width)
    if border_width > 0:
        kw["border_color"] = border
    if height is not None:
        kw["height"] = height
    card = ctk.CTkFrame(parent, **kw)
    draw_card_shell(card, fg=fg, radius=radius, border=border)
    return card


# 兼容旧名（页面/对话框仍在用 make_glass_card）
def make_glass_card(parent, *, fg=None, border=None, radius=T.R.LG,
                    height=None, border_width=0):
    return make_card(parent, fg=fg, radius=radius, height=height,
                     border=border, border_width=border_width)


# =================================================================== 动效总开关
# v4.2：忙时降级 —— 扫描/清理/批量建卡期间，主线程每一毫秒都很宝贵，
# hover 的 4 帧插值动画与卡片描边重绘会跟滚动/建卡抢主线程。
# App 在忙时调用 set_anim_busy(True)，hover/按钮动画降级为“瞬时变色”
# （1 次 itemconfig，无 after 链），视觉差异几乎不可察，但能省掉
# 大量主线程调度；空闲时自动恢复完整动效。
_ANIM_BUSY = False


def set_anim_busy(busy):
    """设置全局动效忙碌标志（扫描/清理中 True，结束 False）。"""
    global _ANIM_BUSY
    _ANIM_BUSY = bool(busy)


def is_anim_busy():
    return _ANIM_BUSY


def animate_card_entrance(card, accent=None, selected=True, delay=0):
    """卡片入场“呼吸描边”（v4.2 新增，廉价感知动画）。

    原理：只改 canvas 上已有的 card_border 图元 outline（单次 <0.1ms），
    全程 2 次 itemconfig + 最多 2 次 after 调度，不触发 CTk configure 级联、
    不重建任何控件。delay 按建卡顺序错开（0/30/60ms…），形成波浪式浮现，
    人眼会觉得“丝滑”，但主线程总开销icker每张卡 <0.3ms。

    参数：
      accent   强调色（None 则用当前主题 PRIMARY）
      selected 卡片最终选中态（决定结束时的描边颜色，与 _refresh_card_state 一致）
      delay    入场延迟 ms（调用方按 idx 错开，实现 stagger）
    """
    try:
        accent = accent or config.C_PRIMARY
        border = config.C_GLASS_BORDER
        flash = _mix_color(border, accent, 0.80)
        final = (_mix_color(border, accent, 0.45) if selected else border)

        def _set(color):
            try:
                if not card.winfo_exists():
                    return False
                card._canvas.itemconfig("card_border", outline=color)
                return True
            except Exception:
                return False

        def _final():
            # shell 可能还没画（draw 在 make_card 后 50ms），tag 不存在则稍后重试一次
            if not _set(final):
                try:
                    card.after(80, lambda: _set(final))
                except Exception:
                    pass

        def _start():
            try:
                if not card.winfo_exists():
                    return
            except Exception:
                return
            _set(flash)
            try:
                card.after(70, _final)
            except Exception:
                _final()

        if delay and delay > 0:
            try:
                card.after(int(delay), _start)
            except Exception:
                _start()
        else:
            _start()
    except Exception:
        pass


def make_skeleton_cards(parent, count=6):
    """骨架占位卡（v4.2 新增）：扫描时先秒出占位，避免“点击后界面冻住”的感觉。

    每张仅 4 个纯色条（无绑定、无 hover、无 shell 重绘），6 张共 ~24 个控件，
    建卡 <10ms；配合 start_skeleton_shimmer 的单一定时器呼吸脉冲，
    用户感知为“正在加载”而非“卡死”。返回 (cards, bars) 供启停/销毁。
    """
    cards = []
    bars = []
    try:
        for _ in range(count):
            card = ctk.CTkFrame(parent, fg_color=config.C_GLASS,
                                corner_radius=T.R.LG, height=110,
                                border_width=0)
            card.pack(fill="x", padx=6, pady=5)
            card.pack_propagate(False)
            # 标题条 + 两行文本条 + 底部徽章条（纯色块，无交互）
            t = ctk.CTkFrame(card, fg_color=config.C_GLASS_3,
                             corner_radius=6, height=16)
            t.pack(fill="x", padx=14, pady=(14, 0))
            t.pack_propagate(False)
            bars.append(t)
            for w in (180, 120):
                b = ctk.CTkFrame(card, fg_color=config.C_GLASS_3,
                                 corner_radius=6, height=11, width=w)
                b.pack(anchor="w", padx=14, pady=(8, 0))
                b.pack_propagate(False)
                bars.append(b)
            f = ctk.CTkFrame(card, fg_color=config.C_GLASS_3,
                             corner_radius=8, height=18, width=90)
            f.pack(anchor="w", padx=14, pady=(10, 0))
            f.pack_propagate(False)
            bars.append(f)
            cards.append(card)
    except Exception:
        pass
    return cards, bars


def start_skeleton_shimmer(widget, bars, interval=380):
    """启动骨架呼吸（单一定时器驱动全部条带，v4.2）。

    每 interval ms 在 base/pulse 两色间切换一次（1 次 tick 改 N 个图元，
    用 _fast_recolor 走 canvas 直改，不走 configure 级联）。
    返回 stop() 可调用对象；widget 销毁后自动停止。
    """
    state = {"on": False, "job": None}

    def _tick():
        state["job"] = None
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        state["on"] = not state["on"]
        target = (config.C_GLASS_HOV if state["on"] else config.C_GLASS_3)
        for b in list(bars):
            try:
                if b.winfo_exists():
                    _fast_recolor(b, target)
            except Exception:
                pass
        try:
            state["job"] = widget.after(interval, _tick)
        except Exception:
            state["job"] = None

    try:
        state["job"] = widget.after(interval, _tick)
    except Exception:
        pass

    def stop():
        job = state.get("job")
        if job is not None:
            try:
                widget.after_cancel(job)
            except Exception:
                pass
            state["job"] = None

    return stop


def bind_hover(widget, base=None, hover=None, *, frames=None, delay=None):
    """悬停平滑变色（走 configure 级联，保证子控件背景跟随）。

    - 必须用 ``configure(fg_color=)`` 而非直接改 canvas 图元：CTk 的透明子控件
      （desc / 名称 / 计数等 Label）在创建时快照了父级底色，只有 configure
      级联才会把新底色下发给它们。直接 itemconfig 卡片 canvas 会导致卡片变浅、
      文字周围却留下深色补丁（悬停“诡异颜色”的根因）。
    - 帧数少（默认 4）、间隔 >= 18ms：不与滚动抢主线程
    - 离开时校验指针是否仍在控件内，避免进入子控件被误判为离开
    """
    base = config.C_GLASS if base is None else base
    hover = config.C_GLASS_HOV if hover is None else hover
    frames = T.AN.HOVER_FRAMES if frames is None else frames
    delay = T.AN.HOVER_DELAY if delay is None else delay
    st = {"job": None, "t": 0.0, "leave": None}

    def _apply(t):
        col = _mix_color(base, hover, t)
        try:
            widget.configure(fg_color=col)
        except Exception:
            pass

    def _run(target):
        # v4.2 忙时降级：批量建卡/扫描期间 hover 直接瞬时变色，不排 after 链
        if _ANIM_BUSY:
            if st["job"] is not None:
                try:
                    widget.after_cancel(st["job"])
                except Exception:
                    pass
                st["job"] = None
            st["t"] = target
            _apply(target)
            return
        if st["job"] is not None:
            try:
                widget.after_cancel(st["job"])
            except Exception:
                pass
            st["job"] = None
        step = (target - st["t"]) / frames

        def tick():
            t = st["t"] + step
            if (step > 0 and t >= target) or (step < 0 and t <= target):
                t = target
            st["t"] = t
            _apply(t)
            st["job"] = None if st["t"] == target else widget.after(delay, tick)

        tick()

    def on_enter(_e):
        if st["leave"] is not None:
            try:
                widget.after_cancel(st["leave"])
            except Exception:
                pass
            st["leave"] = None
        _run(1.0)

    def on_leave(e):
        try:
            x = widget.winfo_pointerx() - widget.winfo_rootx()
            y = widget.winfo_pointery() - widget.winfo_rooty()
            if 0 <= x <= widget.winfo_width() and 0 <= y <= widget.winfo_height():
                return
        except Exception:
            pass
        _run(0.0)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
    return widget


def _set_hand_cursor(widget):
    """给 CTk 控件设置手型光标（Frame 需设内部 canvas）。"""
    try:
        widget.configure(cursor="hand2")
        return
    except Exception:
        pass
    try:
        widget._canvas.configure(cursor="hand2")
    except Exception:
        pass


def make_badge(parent, text, color, *, radius=T.R.PILL, padx=8, pady=2,
               font_size=T.FS.MICRO, height=20, bg=None, bold=True):
    """语义徽章（淡色底 + 同色文字），统一圆角与内距。"""
    base = config.C_GLASS if bg is None else bg
    return ctk.CTkLabel(
        parent, text=text, font=fnt(font_size, "bold" if bold else "normal"),
        text_color=color,
        fg_color=_mix_color(base, color, 0.22 if _is_dark(base) else 0.16),
        corner_radius=radius, padx=padx, pady=pady, height=height)

# =================================================================== 玻璃按钮

class GlassButton(ctk.CTkButton):
    """扁平 + 微高光的现代按钮（v4.0 重设计）。

    与 v3 的差异：
      - 去掉「整体向白提亮」的玻璃浮起（在深色底上显得脏），改为
        「底色 = 面板色与强调色低比例混合」，悬停时提高混合比例 —— 更克制现代。
      - 顶部高光减弱到 5%，仅作材质暗示。
      - 去掉键盘焦点环（点击后蓝圈常驻显杂乱），仅保留悬停变色反馈。
      - 禁用态自动降饱和。
      - v4.3.0 solid 模式：主操作按钮用近实心强调色 + 自动文字色
        （蓝底白字 / 琥珀底深字），一改原来 30% 混合在深色底上发灰、
        琥珀混成"橄榄泥"的廉价感。
    """

    ANIM_STEPS = T.AN.HOVER_FRAMES
    ANIM_DELAY = T.AN.HOVER_DELAY
    TINT       = 0.30    # 常态强调色混合比例
    TINT_HOV   = 0.46    # 悬停混合比例
    HL         = 0.05    # 顶部高光
    HL_INSET   = 8

    def __init__(self, master, text="", command=None, accent=None,
                 parent_bg=None, solid=False, **kw):
        self._accent = accent or config.C_PRIMARY
        self._parent_bg = config.C_GLASS_2 if parent_bg is None else parent_bg
        self._solid = bool(solid)
        self._base_fg, self._hover_fg, self._disabled_fg = self._compute_fg(self._accent)
        self._t = 0.0
        self._shine_job = None
        kw.setdefault("font", fnt(T.FS.BODY, "bold"))
        kw.setdefault("fg_color", self._base_fg)
        kw.setdefault("hover_color", self._base_fg)   # 动画接管
        if "text_color" not in kw:
            kw["text_color"] = (self._solid_text_color() if self._solid
                                else config.C_TEXT)
        kw.setdefault("border_width", 0)
        kw.setdefault("corner_radius", T.R.MD)
        super().__init__(master, text=text, command=command, **kw)
        self._draw_hl()
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        try:
            self._canvas.bind("<Enter>", self._on_enter, add="+")
            self._canvas.bind("<Leave>", self._on_leave, add="+")
        except Exception:
            pass
        # 无焦点环：曾用 canvas 自绘 2px 主色描边表示键盘焦点，
        # 但鼠标点击后焦点会停留在按钮上，蓝圈常驻被误认为选中态/杂边
        # （用户反馈顶部主题/设置/电源按钮及开始清理等按钮上的蓝色矩形），
        # 故去掉绘制，仅保留悬停变色作为反馈。
        self.bind("<FocusOut>", self._on_blur, add="+")

    # ---------- 视觉 ----------
    def _solid_text_color(self):
        """实心按钮文字色：亮底（琥珀/薄荷）配深字，暗底（蓝/红）配白字。"""
        try:
            return "#23272f" if _luma(self._accent) > 150 else "#ffffff"
        except Exception:
            return "#ffffff"

    def _compute_fg(self, accent):
        """按面板深浅配色：深底混强调色提亮，浅底混强调色做淡彩底。

        solid 模式直接用强调色本体（深浅主题通用），悬停向白提亮 14%。
        """
        if getattr(self, "_solid", False):
            base = accent
            hover = _mix_color(accent, "#ffffff", 0.14)
            dis = _mix_color(self._parent_bg, "#000000", 0.25)
            return base, hover, dis
        dark = _is_dark(self._parent_bg)
        if dark:
            base = _mix_color(self._parent_bg, accent, self.TINT)
            hover = _mix_color(self._parent_bg, accent, self.TINT_HOV)
            dis = _mix_color(self._parent_bg, "#000000", 0.25)
        else:
            base = _mix_color(self._parent_bg, accent, 0.14)
            hover = _mix_color(self._parent_bg, accent, 0.24)
            dis = _mix_color(self._parent_bg, "#000000", 0.06)
        return base, hover, dis

    def _draw_hl(self):
        """顶部 1px 高光（弱），营造材质感。"""
        try:
            w = int(getattr(self, "_current_width", 0) or self.winfo_width())
            if w <= 2 * self.HL_INSET:
                return
            self._canvas.delete("glass_hl")
            self._canvas.create_line(
                self.HL_INSET, 1.5, w - self.HL_INSET, 1.5, width=1,
                fill=self._apply_appearance_mode(
                    _mix_color(self._base_fg, "#ffffff", self.HL)),
                tags=("glass_hl",))
        except Exception:
            pass

    def _sync_hl(self):
        try:
            fg = self._disabled_fg if self._state == "disabled" else self._base_fg
            self._canvas.itemconfig(
                "glass_hl",
                fill=self._apply_appearance_mode(_mix_color(fg, "#ffffff", self.HL)))
        except Exception:
            pass

    def set_accent(self, accent):
        self._accent = accent
        self._base_fg, self._hover_fg, self._disabled_fg = self._compute_fg(accent)
        self._t = 0.0
        try:
            self.configure(fg_color=self._base_fg, hover_color=self._base_fg)
            self._apply_look(0.0)
        except Exception:
            pass

    def configure(self, *args, **kwargs):
        """state 切换时同步底色（CTk 默认 disabled 只暗化文字，不改底色）。"""
        if kwargs.get("state") == "disabled":
            kwargs.setdefault("fg_color", self._disabled_fg)
        elif kwargs.get("state") in ("normal", "active"):
            kwargs.setdefault("fg_color", self._base_fg)
        ret = super().configure(*args, **kwargs)
        if kwargs.get("state") in ("disabled", "normal", "active"):
            self._sync_hl()
        return ret

    # ---------- 焦点环（已移除绘制，仅清理历史残留） ----------
    def _on_focus(self, _e=None):
        return

    def _on_blur(self, _e=None):
        try:
            self._canvas.delete("focus_ring")
        except Exception:
            pass

    # ---------- 悬停 ----------
    def _on_enter(self, _e=None):
        super()._on_enter(_e)
        self._animate(1.0)

    def _on_leave(self, _e=None):
        super()._on_leave(_e)
        self._animate(0.0)

    def _animate(self, target):
        job = getattr(self, "_shine_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            self._shine_job = None
        # v4.2 忙时降级：直接跳到目标态，不排 after 链
        if _ANIM_BUSY:
            self._t = target
            self._apply_look(target)
            return
        step = (target - self._t) / self.ANIM_STEPS

        def tick():
            t = self._t + step
            if (step > 0 and t >= target) or (step < 0 and t <= target):
                t = target
            self._t = t
            self._apply_look(t)
            self._shine_job = (None if self._t == target
                               else self.after(self.ANIM_DELAY, tick))

        tick()

    def _apply_look(self, t):
        """整体变色：inner_parts + 文字/图标底色同步，避免文字被矩形框住。"""
        fg = _mix_color(self._base_fg, self._hover_fg, t)
        try:
            c = self._apply_appearance_mode(fg)
            self._canvas.itemconfig("inner_parts", fill=c, outline=c)
            try:
                self._canvas.itemconfig(
                    "glass_hl",
                    fill=self._apply_appearance_mode(
                        _mix_color(fg, "#ffffff", self.HL)))
            except Exception:
                pass
            for attr in ("_text_label", "_image_label"):
                lbl = getattr(self, attr, None)
                if lbl is not None:
                    lbl.configure(bg=c)
        except Exception:
            pass


# 按钮规格：kind -> (高度, 圆角, 字号, 宽度)
_BTN_SPEC = {
    "lg":  dict(height=T.H.BTN_LG, corner_radius=T.R.MD, size=T.FS.H3, width=164),
    "md":  dict(height=T.H.BTN_MD, corner_radius=T.R.MD, size=T.FS.BODY_S, width=96),
    "dlg": dict(height=T.H.BTN_SM, corner_radius=T.R.SM, size=T.FS.BODY_S, width=88),
    "sm":  dict(height=30, corner_radius=T.R.SM, size=T.FS.CAPTION, width=None),
    "icon": dict(height=36, corner_radius=T.R.SM, size=T.FS.BODY, width=36),
}


def glass_btn(master, text, command=None, *, accent=None, kind="md",
              width=None, height=None, parent_bg=None, state=None,
              icon=None, icon_size=18, solid=False, **kw):
    """统一按钮工厂。

    kind: lg 主操作 / md 工具栏次级 / dlg 对话框 / sm 卡片内 / icon 图标按钮
    solid: True 则用近实心强调色（主操作专用，对比度拉满）
    """
    spec = dict(_BTN_SPEC.get(kind, _BTN_SPEC["md"]))
    spec["font"] = fnt(spec.pop("size"), "bold")
    w = spec.pop("width", None)
    h = spec.pop("height", None)
    if width is not None:
        w = width
    if height is not None:
        h = height
    kwargs = dict(spec)
    if w is not None:
        kwargs["width"] = w
    kwargs["height"] = h
    if icon:
        img = ui_icon(icon, icon_size)
        if img is not None:
            kwargs["image"] = img
            kwargs["compound"] = "left"
    kwargs.update(kw)
    btn = GlassButton(master, text=text, command=command, accent=accent,
                      parent_bg=parent_bg, solid=solid, **kwargs)
    if state:
        btn.configure(state=state)
    return btn

# =================================================================== 复合组件

class StatCard(ctk.CTkFrame):
    """统计指标卡：图标胶囊 + 大号数值 + 小标签。横向紧凑排布。

    用于工具栏右侧「已发现文件 / 预计可释放」等关键指标。
    """

    def __init__(self, master, icon, label, color=None, width=150, **kw):
        self.color = color or config.C_PRIMARY
        super().__init__(master, fg_color=config.C_GLASS_3,
                         corner_radius=T.R.MD, width=width,
                         border_width=0, **kw)
        self.pack_propagate(False)
        draw_card_shell(self, fg=config.C_GLASS_3, radius=T.R.MD,
                        border=None, hl=True, shadow=False)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=10, pady=8)

        cap = ctk.CTkLabel(
            row, text="", width=30, height=30, corner_radius=T.R.SM,
            fg_color=_mix_color(config.C_GLASS_3, self.color, 0.32))
        cap.pack(side="left", padx=(0, 9))
        img = ui_icon(icon, 18)
        if img is not None:
            cap.configure(image=img)

        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="both", expand=True)
        self.value = ctk.CTkLabel(col, text="—", font=fnt(T.FS.H3, "bold"),
                                  text_color=config.C_TEXT, anchor="w")
        self.value.pack(anchor="w")
        ctk.CTkLabel(col, text=label, font=fnt(T.FS.MICRO),
                     text_color=config.C_TEXT_3, anchor="w").pack(anchor="w")

    def set_value(self, text, color=None):
        try:
            self.value.configure(text=text,
                                 text_color=color or config.C_TEXT)
        except Exception:
            pass


class NavItem:
    """侧边栏导航项：图标 + 名称 + 右侧数值，支持选中/悬停态。

    v4.0：选中态用「淡强调色底 + 左侧 3px 竖条 + 加粗文字」三重编码，
    不依赖边框，视觉更轻。所有绘制在自身 canvas 内完成。
    """

    def __init__(self, master, icon, text, command, active=False,
                 accent=None, start_pad=10, end_pad=10):
        self._command = command
        self.active = active
        self._accent = accent or config.C_PRIMARY
        self.frame = ctk.CTkFrame(master, fg_color="transparent",
                                  corner_radius=T.R.SM, height=T.H.NAV)
        self.frame.pack(fill="x", pady=1)
        self.frame.pack_propagate(False)

        self._icon = ctk.CTkLabel(self.frame, text="", width=20)
        self._icon.pack(side="left", padx=(start_pad + 2, 8))
        if icon:
            self.set_icon(icon, 18)
        self._text = ctk.CTkLabel(
            self.frame, text=text,
            font=fnt(T.FS.BODY_S, "bold" if active else "normal"),
            text_color=config.C_TEXT if active else config.C_TEXT_3,
            anchor="w")
        self._text.pack(side="left", fill="x", expand=True)
        self._count = ctk.CTkLabel(
            self.frame, text="", font=fnt(T.FS.MICRO, "bold"),
            text_color=config.C_TEXT_4, anchor="e")
        self._count.pack(side="right", padx=(4, end_pad))

        for w in (self.frame, self._icon, self._text, self._count):
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<Button-1>", self._on_click, add="+")
            _set_hand_cursor(w)
        self._paint()

    # ---------- 交互 ----------
    def _on_click(self, _e=None):
        if self._command:
            self._command()

    def _on_enter(self, _e=None):
        if self.active:
            return
        try:
            self.frame.configure(fg_color=config.C_GLASS_HOV)
        except Exception:
            pass

    def _on_leave(self, _e=None):
        self._paint()

    # ---------- 绘制 ----------
    def _paint(self):
        """按 active 状态绘制底色 + 左侧强调条（canvas 内绘制，不越界）。"""
        try:
            if self.active:
                self.frame.configure(
                    fg_color=_mix_color(config.C_GLASS_2, self._accent, 0.16))
            else:
                self.frame.configure(fg_color="transparent")
            self._text.configure(
                text_color=config.C_TEXT if self.active else config.C_TEXT_3,
                font=fnt(T.FS.BODY_S, "bold" if self.active else "normal"))
            self._count.configure(
                text_color=(self._accent if self.active else config.C_TEXT_4))
            self._draw_accent()
        except Exception:
            pass

    def _draw_accent(self):
        """选中态左侧竖条（canvas 内绘制，圆角，不越出控件）。"""
        try:
            cv = self.frame._canvas
            cv.delete("nav_accent")
            if not self.active:
                return
            h = self.frame.winfo_height() or T.H.NAV
            if h <= 8:
                return
            # 竖条居中、上下各留 9px，圆角胶囊形
            cv.create_polygon(
                rounded_poly(0, 9, 3, h - 9, 1.5),
                smooth=True, fill=self._accent, outline="",
                tags=("nav_accent",))
        except Exception:
            pass

    def set_active(self, active):
        self.active = active
        self._paint()

    def set_count(self, text):
        try:
            self._count.configure(text=text)
        except Exception:
            pass

    def set_icon(self, name, size=18):
        img = ui_icon(name, size)
        if img is not None:
            try:
                self._icon.configure(image=img)
            except Exception:
                pass


class SegmentedControl(ctk.CTkFrame):
    """分段选择器（iOS 风格）：胶囊底 + 滑动选中块。

    用于设置页主题切换等二选一/三选一场景，比按钮组更紧凑明确。

    注意：形参不能叫 ``options`` —— 会遮蔽 ``tkinter.Misc._options``，
    导致 ``TypeError: 'list' object is not callable``。用 ``items``。
    """

    def __init__(self, master, items, command=None, accent=None,
                 height=34, width=None, **kw):
        self._items = list(items)              # [(value, label)]
        self._command = command
        self._accent = accent or config.C_PRIMARY
        self._value = self._items[0][0] if self._items else None
        track = config.C_GLASS_3
        super().__init__(master, fg_color=track, corner_radius=height // 2,
                         height=height, width=width or 60 * len(self._items),
                         **kw)
        if width is None:
            self.configure(width=60 * max(1, len(self._items)))
        self.pack_propagate(False)
        self._height = height
        self._track = track

        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=3, pady=3)
        self._btns = {}
        for val, label in self._items:
            b = ctk.CTkLabel(self._inner, text=label,
                             font=fnt(T.FS.CAPTION, "bold"),
                             text_color=config.C_TEXT_3,
                             corner_radius=(height - 6) // 2,
                             fg_color="transparent")
            b.pack(side="left", fill="both", expand=True, padx=1)
            b.bind("<Button-1>", lambda _e, v=val: self.set_value(v))
            _set_hand_cursor(b)
            self._btns[val] = b

    def set_value(self, value, notify=True):
        if value not in self._btns:
            return
        self._value = value
        for val, b in self._btns.items():
            on = val == value
            try:
                b.configure(
                    fg_color=(_mix_color(self._track, self._accent, 0.85) if on
                              else "transparent"),
                    text_color=("#ffffff" if on else config.C_TEXT_3))
            except Exception:
                pass
        if notify and self._command:
            self._command(value)

    # 兼容别名（设置页用 set(value) 初始化选中态）
    def set(self, value, notify=False):
        self.set_value(value, notify=notify)

    def get(self):
        return self._value


class SectionTitle(ctk.CTkFrame):
    """区块小标题：左侧强调竖条 + 标题 + 右侧可选说明。"""

    def __init__(self, master, text, sub=None, color=None, **kw):
        color = color or config.C_PRIMARY
        super().__init__(master, fg_color="transparent", **kw)
        bar = ctk.CTkFrame(self, fg_color=color, width=3,
                           corner_radius=2, height=15)
        bar.pack(side="left", padx=(0, 9), pady=2)
        ctk.CTkLabel(self, text=text, font=fnt(T.FS.H3, "bold"),
                     text_color=config.C_TEXT, anchor="w").pack(side="left")
        if sub:
            ctk.CTkLabel(self, text=sub, font=fnt(T.FS.CAPTION),
                         text_color=config.C_TEXT_4).pack(side="left", padx=(10, 0))


class EmptyState(ctk.CTkFrame):
    """空状态占位：大图标 + 标题 + 说明 + 可选插槽。"""

    def __init__(self, master, icon="empty", title="", desc="", icon_size=48,
                 **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ic = ctk.CTkLabel(self, text="")
        ic.pack(pady=(0, 14))
        img = ui_icon(icon, icon_size)
        if img is not None:
            ic.configure(image=img)
        if title:
            ctk.CTkLabel(self, text=title, font=fnt(T.FS.H2, "bold"),
                         text_color=config.C_TEXT).pack()
        if desc:
            ctk.CTkLabel(self, text=desc, font=fnt(T.FS.BODY_S),
                         text_color=config.C_TEXT_3,
                         justify="center").pack(pady=(8, 0))


class ProgressBar(ctk.CTkFrame):
    """自绘进度条：圆角轨道 + 圆角填充 + 顶部微光。

    不使用 CTkProgressBar —— 它每次 set() 都重建字形路径；本实现在
    canvas 上直接改 coords，成本 <0.05ms。
    """

    def __init__(self, master, height=8, color=None, **kw):
        color = color or config.C_PRIMARY
        super().__init__(master, fg_color="transparent", height=height, **kw)
        self._h = height
        self._color = color
        self._value = 0.0
        self._cv = tk.Canvas(self, height=height, highlightthickness=0,
                             bd=0, bg=config.C_BG_ALT)
        self._cv.pack(fill="x", expand=True)
        self._cv.bind("<Configure>", lambda _e: self._redraw())

    def set(self, value):
        self._value = max(0.0, min(1.0, float(value)))
        self._redraw()

    def _redraw(self):
        try:
            w = self._cv.winfo_width()
            h = self._h
            if w <= 2:
                return
            self._cv.delete("all")
            r = h / 2.0
            self._cv.create_polygon(rounded_poly(0, 0, w, h, r), smooth=True,
                                    fill=config.C_GLASS_3, outline="")
            fw = max(0.0, w * self._value)
            if fw > 1:
                r2 = min(r, fw / 2.0)
                self._cv.create_polygon(
                    rounded_poly(0, 0, fw, h, r2), smooth=True,
                    fill=self._color, outline="")
                if fw > 12:
                    self._cv.create_line(
                        r2, 1.5, fw - r2, 1.5, width=1,
                        fill=_mix_color(self._color, "#ffffff", 0.35))
        except Exception:
            pass


class Dropdown(ctk.CTkFrame):
    """轻量下拉选择器（替代 CTkOptionMenu 的厚重外观）。"""

    def __init__(self, master, values, command=None, width=180,
                 placeholder="请选择", **kw):
        super().__init__(master, fg_color=config.C_GLASS_3,
                         corner_radius=T.R.SM, height=T.H.BTN_MD,
                         width=width, border_width=0, **kw)
        self.pack_propagate(False)
        self._values = list(values)
        self._command = command
        self._value = None
        self._popup = None
        draw_card_shell(self, fg=config.C_GLASS_3, radius=T.R.SM,
                        border=config.C_GLASS_BORDER, hl=False, shadow=False)
        self._lbl = ctk.CTkLabel(self, text=placeholder,
                                 font=fnt(T.FS.BODY_S), text_color=config.C_TEXT_3,
                                 anchor="w")
        self._lbl.pack(side="left", fill="both", expand=True, padx=(12, 4))
        caret = ctk.CTkLabel(self, text="⌄", font=fnt(T.FS.BODY),
                             text_color=config.C_TEXT_3, width=20)
        caret.pack(side="right", padx=(0, 8))
        for w in (self, self._lbl, caret):
            w.bind("<Button-1>", self._toggle)
            _set_hand_cursor(w)

    def _toggle(self, _e=None):
        if self._popup is not None:
            self._close()
            return
        try:
            top = tk.Toplevel(self)
            top.wm_overrideredirect(True)
            top.attributes("-topmost", True)
            style_popup(top)
            self._popup = top
            box = ctk.CTkFrame(top, fg_color=config.C_GLASS_2,
                               corner_radius=T.R.SM, border_width=0)
            box.pack()
            draw_card_shell(box, fg=config.C_GLASS_2, radius=T.R.SM,
                            border=config.C_GLASS_BORDER, hl=False, shadow=False)
            for v in self._values:
                it = ctk.CTkLabel(box, text=str(v), font=fnt(T.FS.BODY_S),
                                  text_color=config.C_TEXT, anchor="w",
                                  corner_radius=T.R.SM, height=30, width=160)
                it.pack(fill="x", padx=6, pady=1)
                it.bind("<Button-1>", lambda _e, val=v: self._pick(val))
                it.bind("<Enter>", lambda _e, b=it: b.configure(
                    fg_color=config.C_GLASS_HOV))
                it.bind("<Leave>", lambda _e, b=it: b.configure(
                    fg_color="transparent"))
                _set_hand_cursor(it)
            self.update_idletasks()
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height() + 4
            top.wm_geometry(f"+{x}+{y}")
            top.bind("<FocusOut>", lambda _e: self._close())
        except Exception:
            self._close()

    def _pick(self, value):
        self._value = value
        try:
            self._lbl.configure(text=str(value), text_color=config.C_TEXT)
        except Exception:
            pass
        self._close()
        if self._command:
            self._command(value)

    def _close(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None

    def get(self):
        return self._value

    def set(self, value):
        self._pick(value)


class Toggle(ctk.CTkFrame):
    """圆角开关（iOS 风格）—— canvas 自绘，不依赖 CTkSwitch 的厚重外形。"""

    W, H = 46, 26

    def __init__(self, master, command=None, value=False, **kw):
        super().__init__(master, fg_color="transparent", width=self.W,
                         height=self.H, **kw)
        self.pack_propagate(False)
        self._command = command
        self._on = bool(value)
        self._cv = tk.Canvas(self, width=self.W, height=self.H,
                             highlightthickness=0, bd=0, bg=config.C_BG_ALT)
        self._cv.pack()
        self._cv.bind("<Button-1>", self._toggle)
        _set_hand_cursor(self._cv)
        self._paint()

    def _toggle(self, _e=None):
        self._on = not self._on
        self._paint()
        if self._command:
            self._command(self._on)

    def _paint(self):
        try:
            self._cv.delete("all")
            w, h = self.W, self.H
            track = (config.C_PRIMARY if self._on else config.C_GLASS_3)
            self._cv.create_polygon(rounded_poly(0, 0, w, h, h / 2),
                                    smooth=True, fill=track, outline="")
            cx = (w - h / 2 - 3) if self._on else (h / 2 + 3)
            self._cv.create_oval(cx - h / 2 + 3, 3, cx + h / 2 - 3, h - 3,
                                 fill="#ffffff", outline="")
        except Exception:
            pass

    def get(self):
        return self._on

    def set(self, value):
        self._on = bool(value)
        self._paint()
