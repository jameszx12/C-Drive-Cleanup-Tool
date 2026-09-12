# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 v4.0 · 主窗口（CleanerApp）。

v4.0 界面重构（设计系统驱动）
  - 颜色 / 字号 / 圆角 / 间距 / 高度 / 动效全部来自 theme.py 令牌，
    页面不再出现魔法数字，整体换肤只需改令牌。
  - 三级面板明度分层（BG → SURFACE → SURFACE_2 → SURFACE_3）替代重边框。
  - 头部：大标题 + 版本胶囊 + 图标按钮组（工具条式）。
  - 侧边栏：胶囊搜索框 + 分组导航（选中态 = 淡强调底 + 左侧竖条）。
  - 工具栏：主操作区 + 分隔线 + 编辑区 + 右侧统计指标卡。
  - 卡片：图标胶囊 + 标题 + 大小 + 描述 + 底行徽章/操作，
    选中态 = 1px 强调描边 + 左侧 3px 竖条（全部 canvas 内绘制）。
  - 状态栏：自绘进度条（<0.05ms/次）+ 状态点 + 百分比 + 已选统计。
  - 键盘：Enter 扫描 / Ctrl+A 全选 / Ctrl+Shift+A 全不选 / F5 重扫。
"""
import os
import sys
import queue
import threading
import tkinter as tk
import tkinter.messagebox as mb
from concurrent.futures import ThreadPoolExecutor
import customtkinter as ctk

import config
import theme as T
from config import (APP_NAME, AUTHOR, VERSION, load_config, save_config,
                    apply_theme, _logger, detect_system_theme)
from widgets import (make_glass_card, make_card, draw_card_shell, bind_hover,
                     fnt, mono_fnt, _mix_color, _is_dark, rounded_poly,
                     fmt_size, rule_visual, _set_hand_cursor,
                     GlassButton, glass_btn, ui_icon, rule_icon_photo,
                     make_badge, Tooltip, NavItem, StatCard, SegmentedControl,
                     SectionTitle, EmptyState, ProgressBar, Toggle, Dropdown,
                     style_popup, animate_card_entrance, make_skeleton_cards,
                     start_skeleton_shimmer, set_anim_busy)
from engine import (scan_rule, scan_rules_parallel, clean_files,
                    filter_files_by_selection, open_in_explorer)
from rules import build_rules
from icons import get_app_icon
from glass import apply_window_backdrop
from dialogs import FolderDetailDialog, PackageDetailDialog, SettingsDialog

# 侧边栏分类元信息：cat -> (图标 key, 显示名, 强调色)
CAT_META = {
    "system": ("nav_system", "系统垃圾", "#60a5fa"),
    "browser": ("nav_browser", "浏览器", config.C_SUCCESS),
    "app": ("nav_app", "应用缓存", config.C_WARN),
    "dev": ("nav_dev", "开发工具", config.C_INFO),
    "game": ("nav_game", "游戏平台", "#a855f7"),
    "media": ("nav_media", "媒体工具", "#f472b6"),
    "cloud": ("nav_cloud", "云盘", "#22d3ee"),
    "driver": ("nav_driver", "驱动显卡", "#94a3b8"),
    "deep": ("nav_deep", "深度扫描", "#a78bfa"),
    "update": ("nav_update", "更新安装包", config.C_INFO),
}

# SidebarItem：v4.0 起由 widgets.NavItem 实现，此处保留旧名以兼容历史引用。
SidebarItem = NavItem


class CleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # v4.3.0：标题栏更干净（作者/版本移到界面内展示）；设置任务栏/标题图标
        self.title(f"{APP_NAME} {VERSION}")
        try:
            _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            _ico = os.path.join(_base, "app_icon.ico")
            if os.path.isfile(_ico):
                self.iconbitmap(_ico)
        except Exception:
            pass
        self._init_window_geometry()
        self.cfg = load_config()
        self.theme_pref = self.cfg.get("theme", "dark")   # 用户偏好：light/dark/auto
        self.glass_mode = bool(self.cfg.get("glass_mode", False))
        self.theme_name = (detect_system_theme() if self.theme_pref == "auto"
                           else self.theme_pref)
        apply_theme(self.theme_name)
        ctk.set_appearance_mode(self.theme_name)
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=config.C_BG)

        self.rules = build_rules()
        self.row_widgets = []
        self.scanning = False
        self.cleaning = False
        self.has_scanned = False
        self._closing = False
        self._cancel_requested = False
        self._cancel_event = threading.Event()
        self._settings_dlg = None
        self._open_dialogs = {}
        # 侧边栏分类过滤 / 搜索 / 勾选状态（跨过滤与主题切换保留）
        self._current_cat = None          # None=全部
        self._search_text = ""
        self._visible_rules = list(self.rules)
        self._visible_keys = {r.get("key") for r in self.rules}
        self._sel_state = {}              # {rule_key: bool}
        self._side_items = {}             # cat -> NavItem
        # 响应式网格：根据列表区宽度自动决定每行卡片数（1-4 列）
        self._cols = 2
        self._max_cols_cfg = 2
        self._col_width = 480
        # v4.2 流畅度：图标加载共享线程池（原来每张卡一个线程，40+ 线程争抢），
        # 待建卡队列 + 分批刷新（每帧最多 6 张，主线程不被建卡淹没），
        # 骨架屏占位（点击扫描瞬间即有反馈，不再“冻住”）。
        self._icon_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="icon")
        self._pending_cards = []      # 已扫完待建卡的 rule（仅主线程触碰）
        self._flush_job = None        # 分批建卡的 after 句柄
        self._scan_done = 0
        self._scan_total = 0
        self._skeleton_host = None
        self._skeleton_stop = None
        # v4.2 线程安全：后台线程绝不直接碰 Tk（after 跨线程会
        # RuntimeError/死锁），只往 queue 里放结果，主线程定时来取。
        self._scan_queue = None
        self._scan_gen = 0            # 扫描代际（防止旧轮询串台）
        self._clean_queue = None
        self._clean_gen = 0

        self._build_shell()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Return>", self._on_return)
        self.bind("<Control-a>", lambda _e: self._set_all(True))
        self.bind("<Control-A>", lambda _e: self._set_all(True))
        self.bind("<Control-Shift-a>", lambda _e: self._set_all(False))
        self.bind("<Control-Shift-A>", lambda _e: self._set_all(False))
        self.bind("<F5>", lambda _e: self.start_scan())
        self.report_callback_exception = self._on_callback_exception

    @staticmethod
    def _on_callback_exception(exc_type, exc_value, exc_tb):
        import traceback
        if "invalid command name" in str(exc_value):
            return  # 已销毁控件的迟发回调，安全忽略
        traceback.print_exception(exc_type, exc_value, exc_tb)

    def _on_return(self, _e=None):
        """全局回车 = 开始扫描，但焦点在输入框时除外。

        否则在侧栏搜索框里敲回车也会触发扫描（用户本意只是确认搜索）。
        """
        try:
            fw = self.focus_get()
            if isinstance(fw, (ctk.CTkEntry, tk.Entry)):
                return
        except Exception:
            pass
        self.start_scan()

    # ---------- 窗口几何 ----------
    def _init_window_geometry(self):
        """按屏幕实际可用尺寸自适应初始窗口，并居中。

        高 DPI / 小屏（如 1536×864 @125%）上固定 1280×840 会超出屏幕，
        故取「屏幕的 88%」为基准，并夹在 [1080×700, 1440×920] 区间内。
        """
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        except Exception:
            sw, sh = 1920, 1080
        w = max(1080, min(1440, int(sw * 0.88)))
        h = max(700, min(920, int(sh * 0.90)))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 12)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(1000, 660)

    # ---------- 窗口背景 ----------
    def _apply_backdrop(self):
        """窗口背景：毛玻璃开启时用系统 Acrylic，否则纯色不透明。

        v4.0 起默认关闭毛玻璃（用户反馈卡片彩色边缘 + 追求干净观感）。
        """
        try:
            apply_window_backdrop(self, config.C_BG, self.glass_mode)
            return
        except Exception:
            pass
        try:
            self.configure(fg_color=config.C_BG)
        except Exception:
            pass

    # ================= 布局 =================
    def _build_shell(self):
        """按当前主题构建主界面；主题切换时复用。

        v4.0 布局（间距严格取自 T.SP，避免各处魔法数字）：
          ┌ Header ──────────────────────────────┐  高 76，SURFACE_2
          ├ Sidebar ┬ Main ──────────────────────┤
          │ 搜索    │ Toolbar (66, SURFACE_2)     │
          │ 导航    │ 卡片网格（滚动）             │
          ├ Status ──────────────────────────────┤  高 56，SURFACE_2
          └──────────────────────────────────────┘
        """
        self._apply_backdrop()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.content.lift()

        self._build_header()
        body = ctk.CTkFrame(self.content, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=T.SP.LG, pady=(T.SP.MD, 0))
        self._build_sidebar(body)
        main = ctk.CTkFrame(body, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=(T.SP.MD, 0))
        self._build_toolbar(main)
        self._build_list_area(main)
        self._build_status_bar()

    def _toggle_theme(self):
        """循环切换主题：light → dark → auto → light。"""
        order = ["light", "dark", "auto"]
        cur = self.theme_pref if self.theme_pref in order else "dark"
        self.apply_theme_pref(order[(order.index(cur) + 1) % len(order)])

    def apply_theme_pref(self, pref):
        """按指定偏好应用主题并重建界面（头部按钮与设置对话框共用）。

        auto 模式根据系统主题动态应用（darkdetect），重启自动跟随系统变化。
        扫描/清理中拒绝切换，返回 False。
        """
        if self.scanning or self.cleaning:
            return False
        # 先关闭所有已打开的详情对话框
        for dlg in list(self._open_dialogs.values()):
            try:
                dlg._on_close()
            except Exception:
                pass
        self._open_dialogs.clear()
        self.theme_pref = pref
        self.theme_name = (detect_system_theme() if pref == "auto" else pref)
        self.cfg["theme"] = pref
        save_config(self.cfg)
        apply_theme(self.theme_name)
        ctk.set_appearance_mode(self.theme_name)
        self._rebuild_ui()
        return True

    def _rebuild_ui(self):
        """主题切换后整体重建界面，并恢复状态（扫描结果 / 计数 / 进度）。"""
        self.content.destroy()
        self.row_widgets = []
        self._cols = 2
        self._max_cols_cfg = 2
        self._col_width = 480
        self._build_shell()
        self._sync_sidebar_counts()
        if self.has_scanned:
            self._apply_visible_rules()
            total_count = sum(r.get("_count", 0) for r in self.rules)
            total_size = sum(r.get("_size", 0) for r in self.rules)
            self.card_count.set_value(f"{total_count:,}", config.C_SUCCESS)
            self.card_space.set_value(fmt_size(total_size), config.C_SUCCESS)
            self._set_status("主题已切换；可继续选择或清理扫描结果。")
            self._set_progress(1)

    # ---------- 头部 ----------
    def _build_header(self):
        """顶部栏：应用标识 + 副标题（左），图标按钮组（右）。

        v4.0：高度 76、SURFACE_2 面板、无重边框；右侧图标按钮统一 38×38
        圆角 10 的「工具条」风格，hover 用强调色低比例混色。
        """
        hdr = make_card(self.content, fg=config.C_GLASS_2, height=T.H.HEADER)
        hdr.pack(fill="x", padx=T.SP.LG, pady=(T.SP.LG, 0))
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(T.SP.XL, 0))
        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(anchor="w", pady=(14, 0))

        # 应用标识：圆角方块 + 线性图标（不用 emoji，保证跨设备一致）
        # v4.3.0：胶囊底加深（0.26→0.34），品牌蓝在深色底上不再发灰
        badge = ctk.CTkLabel(
            row, text="", width=42, height=42, corner_radius=T.R.MD,
            fg_color=_mix_color(config.C_GLASS_2, config.C_PRIMARY, 0.34))
        badge.pack(side="left", padx=(0, T.SP.MD))
        logo = ui_icon("empty", 26)
        if logo is not None:
            badge.configure(image=logo)
        else:
            badge.configure(text="◈", font=fnt(T.FS.H2),
                            text_color=config.C_PRIMARY)

        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left")
        title_row = ctk.CTkFrame(col, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(title_row, text=APP_NAME, font=fnt(T.FS.H1, "bold"),
                     text_color=config.C_TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(
            title_row, text=VERSION, font=fnt(T.FS.MICRO, "bold"),
            text_color=config.C_PRIMARY,
            fg_color=_mix_color(config.C_GLASS_2, config.C_PRIMARY, 0.20),
            corner_radius=T.R.PILL, padx=7, pady=1).pack(side="left", padx=(9, 0))
        ctk.CTkLabel(
            col, text="清理系统与应用缓存 / 临时 / 日志 · 绝不触碰个人文件",
            font=fnt(T.FS.CAPTION), text_color=config.C_TEXT_3,
            anchor="w").pack(anchor="w", pady=(3, 0))

        # 右侧工具条
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=(0, T.SP.XL), pady=T.SP.XL)
        theme_icon = {"light": "sun", "dark": "moon", "auto": "sun_moon"}.get(
            self.theme_pref, "moon")
        for icon, cmd, tip, accent in (
            (theme_icon, self._toggle_theme, "切换主题（浅色 / 深色 / 跟随系统）",
             config.C_PRIMARY),
            ("settings", self._open_settings, "打开设置", config.C_INFO),
            ("power", self._on_close, "退出程序", config.C_DANGER),
        ):
            b = glass_btn(right, "", cmd, accent=accent, kind="icon",
                          width=38, height=38, parent_bg=config.C_GLASS_2,
                          icon=icon, icon_size=19)
            b.pack(side="left", padx=(T.SP.SM, 0))
            Tooltip(b, tip)
        self.btn_theme = right.winfo_children()[0]
        self.btn_settings = right.winfo_children()[1]
        self.btn_exit = right.winfo_children()[2]

    # ---------- 侧边栏 ----------
    def _build_sidebar(self, parent):
        """左侧导航：搜索框 + 分类列表 + 底部信息。

        v4.0：整体 SURFACE_2 面板；导航项选中 = 淡强调底 + 左侧 3px 竖条。
        搜索框用 CTkEntry 自带圆角 + 描边（不叠加自绘描边，避免重复边框）。
        """
        wrap = ctk.CTkFrame(parent, fg_color=config.C_GLASS_2,
                            corner_radius=T.R.LG, width=224)
        wrap.pack(side="left", fill="y")
        wrap.pack_propagate(False)
        draw_card_shell(wrap, fg=config.C_GLASS_2, radius=T.R.LG,
                        border=config.C_GLASS_BORDER, hl=False, shadow=False)

        # 标题
        ctk.CTkLabel(wrap, text="清理分类", font=fnt(T.FS.H3, "bold"),
                     text_color=config.C_TEXT, anchor="w").pack(
            fill="x", padx=T.SP.LG, pady=(T.SP.LG, T.SP.SM))

        # 搜索框：图标 + 输入（CTkEntry 自带描边圆角）
        sbox = ctk.CTkFrame(wrap, fg_color=config.C_GLASS_3,
                            corner_radius=T.R.MD, height=T.H.INPUT)
        sbox.pack(fill="x", padx=T.SP.MD, pady=(0, T.SP.SM))
        sbox.pack_propagate(False)
        draw_card_shell(sbox, fg=config.C_GLASS_3, radius=T.R.MD,
                        border=config.C_LINE_3, hl=False, shadow=False)
        s_icon = ui_icon("search", 15)
        if s_icon is not None:
            ctk.CTkLabel(sbox, text="", image=s_icon, width=16).pack(
                side="left", padx=(T.SP.MD, 2))
        else:
            ctk.CTkLabel(sbox, text="⌕", font=fnt(T.FS.H3),
                         text_color=config.C_TEXT_4, width=16).pack(
                side="left", padx=(T.SP.MD, 2))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search_change())
        self.search_entry = ctk.CTkEntry(
            sbox, textvariable=self.search_var,
            placeholder_text="搜索清理项", font=fnt(T.FS.BODY_S),
            height=T.H.INPUT - 8, fg_color="transparent", border_width=0,
            text_color=config.C_TEXT, corner_radius=0)
        self.search_entry.pack(side="left", fill="both", expand=True,
                               padx=(2, T.SP.SM))

        # 底部信息：先 pack（side=bottom），保证它在导航区之前占据空间，
        # 否则 nav_scroll 的 expand=True 会把它挤出可视区。
        about = ctk.CTkFrame(wrap, fg_color="transparent", height=46)
        about.pack(side="bottom", fill="x")
        about.pack_propagate(False)
        ctk.CTkLabel(about, text=f"{VERSION} · by {AUTHOR}",
                     font=fnt(T.FS.MICRO), text_color=config.C_TEXT_4,
                     anchor="w").pack(fill="x", padx=T.SP.LG, pady=(T.SP.MD, 0))
        ctk.CTkLabel(about, text="安全清理 · 可恢复",
                     font=fnt(T.FS.MICRO), text_color=config.C_TEXT_4,
                     anchor="w").pack(fill="x", padx=T.SP.LG, pady=(2, T.SP.SM))

        # 导航滚动区（expand 填满剩余空间）
        nav_scroll = ctk.CTkScrollableFrame(
            wrap, fg_color="transparent",
            scrollbar_button_color=config.C_GLASS_3,
            scrollbar_button_hover_color=config.C_LINE_3)
        nav_scroll.pack(fill="both", expand=True, padx=(T.SP.SM, 2))

        ctk.CTkLabel(nav_scroll, text="总览", font=fnt(T.FS.MICRO, "bold"),
                     text_color=config.C_TEXT_4, anchor="w").pack(
            fill="x", padx=T.SP.SM, pady=(T.SP.SM, 2))
        self._all_item = NavItem(
            nav_scroll, "nav_all", "全部项目",
            lambda: self._select_cat(None), active=True,
            accent=config.C_PRIMARY)
        self._side_items[None] = self._all_item

        seen = []
        for r in self.rules:
            c = r.get("cat")
            if c and c not in seen:
                seen.append(c)
        if seen:
            ctk.CTkLabel(nav_scroll, text="分类", font=fnt(T.FS.MICRO, "bold"),
                         text_color=config.C_TEXT_4, anchor="w").pack(
                fill="x", padx=T.SP.SM, pady=(T.SP.MD, 2))
        for cat in seen:
            icon, name, color = CAT_META.get(cat, ("nav_app", cat, config.C_PRIMARY))
            self._side_items[cat] = NavItem(
                nav_scroll, icon, name, lambda c=cat: self._select_cat(c),
                accent=color)

    def _on_search_change(self, *_):
        """搜索防抖：连续输入时只在停顿 200ms 后重建一次卡片。"""
        try:
            if getattr(self, "_search_job", None) is not None:
                self.after_cancel(self._search_job)
        except Exception:
            pass
        try:
            self._search_job = self.after(200, self._do_search_change)
        except Exception:
            self._do_search_change()

    def _do_search_change(self):
        self._search_job = None
        try:
            if self._closing or not self.winfo_exists():
                return
            # v4.3.0：扫描/清理中不重建列表（搜索框此时已禁用，此为兜底）
            if self.scanning or self.cleaning:
                return
            self._search_text = self.search_var.get().strip().lower()
            self._apply_visible_rules()
            self._refresh_sel_buttons()
        except Exception:
            pass

    def _select_cat(self, cat):
        if self.scanning or self.cleaning:
            return
        if cat == self._current_cat:
            return
        self._current_cat = cat
        for key, item in self._side_items.items():
            item.set_active(key == cat)
        self._apply_visible_rules()
        self._refresh_sel_buttons()

    def _sync_sidebar_counts(self):
        """扫描结果汇总到侧边栏（未扫描显示 —）。"""
        try:
            has = self.has_scanned
            # 全部项目：显示总数/总体积
            if has:
                total = sum(r.get("_count", 0) for r in self.rules)
                size = sum(r.get("_size", 0) for r in self.rules)
                self._all_item.set_count(f"{fmt_size(size)}" if total else "0")
            else:
                self._all_item.set_count("—")
            for cat, item in self._side_items.items():
                if cat is None:
                    continue
                rs = [r for r in self.rules if r.get("cat") == cat]
                if has:
                    n = sum(r.get("_count", 0) for r in rs)
                    s = sum(r.get("_size", 0) for r in rs)
                    item.set_count(fmt_size(s) if n else "0")
                else:
                    item.set_count("—")
        except Exception:
            pass

    # ---------- 工具栏 ----------
    def _build_toolbar(self, parent):
        """主操作栏：核心操作（扫描/清理/取消） | 编辑（全选/全不选） | 统计指标。

        v4.0：高 66、SURFACE_2 面板；分组之间用 1px 极弱分隔线；
        统计指标改用 StatCard（图标胶囊 + 大号数值 + 小标签）。
        """
        bar = make_card(parent, fg=config.C_GLASS_2, height=T.H.TOOLBAR)
        bar.pack(fill="x", pady=(0, T.SP.SM))
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=T.SP.MD, pady=T.SP.MD)

        # ---- 核心操作 ----
        core = ctk.CTkFrame(inner, fg_color="transparent")
        core.pack(side="left")
        self.btn_scan = glass_btn(core, "开始扫描", self.start_scan,
                                  accent=config.C_PRIMARY, kind="lg",
                                  parent_bg=config.C_GLASS_2, solid=True,
                                  icon="scan", icon_size=19)
        self.btn_scan.pack(side="left", padx=(0, T.SP.SM))

        self.btn_clean = glass_btn(core, "清理选中", self.start_clean,
                                   accent=config.C_WARN, kind="lg",
                                   parent_bg=config.C_GLASS_2, solid=True,
                                   icon="clean", icon_size=19)
        self.btn_clean.pack(side="left", padx=(0, T.SP.SM))

        self.btn_cancel = glass_btn(core, "取消", self._request_cancel,
                                    accent=config.C_DANGER, kind="md",
                                    parent_bg=config.C_GLASS_2,
                                    icon="cancel", icon_size=17, state="disabled")
        self.btn_cancel.pack(side="left")

        # ---- 分隔线 ----
        ctk.CTkFrame(inner, fg_color=config.C_LINE_2, width=1).pack(
            side="left", fill="y", padx=T.SP.LG, pady=2)

        # ---- 编辑组 ----
        edit = ctk.CTkFrame(inner, fg_color="transparent")
        edit.pack(side="left")
        self.btn_all = glass_btn(edit, "全选", lambda: self._set_all(True),
                                 accent=config.C_PRIMARY, kind="md",
                                 parent_bg=config.C_GLASS_2,
                                 icon="sel_all_off", icon_size=17)
        self.btn_all.pack(side="left", padx=(0, T.SP.SM))
        self.btn_none = glass_btn(edit, "全不选", lambda: self._set_all(False),
                                  accent=config.C_TEXT_4, kind="md",
                                  parent_bg=config.C_GLASS_2,
                                  icon="sel_none_off", icon_size=17)
        self.btn_none.pack(side="left")

        # ---- 右侧指标卡 ----
        stats = ctk.CTkFrame(inner, fg_color="transparent")
        stats.pack(side="right")
        self.card_count = StatCard(stats, "file", "已发现文件",
                                   color=config.C_PRIMARY, width=152)
        self.card_count.pack(side="left", padx=(0, T.SP.SM))
        self.card_space = StatCard(stats, "drive", "预计可释放",
                                   color=config.C_SUCCESS, width=152)
        self.card_space.pack(side="left")
        # 兼容旧引用（对话框与主题切换里更新这两个标签）
        self.summary_label = self.card_count.value
        self.metric_label = self.card_space.value

    # ---------- 列表区 ----------
    def _build_list_area(self, parent):
        """卡片网格滚动区 + 欢迎页叠层。

        v4.0：滚动区底色 = BG（比面板更深一档），卡片用 SURFACE，
        形成明确的「面板浮在背景上」层次；卡片间隙也不再透出窗口背景。

        欢迎页不放进滚动区 —— 否则会被内容高度 shrink-wrap 导致无法居中。
        改为在滚动区父容器上加一层 ``place`` 叠层，始终相对**可视区**居中。
        """
        # 外层容器：承载「滚动区」与「欢迎页叠层」两个兄弟组件
        self.list_area = ctk.CTkFrame(parent, fg_color="transparent")
        self.list_area.pack(fill="both", expand=True, pady=(0, T.SP.SM))

        self.scroll = ctk.CTkScrollableFrame(
            self.list_area, fg_color=config.C_BG_ALT, corner_radius=T.R.MD,
            scrollbar_button_color=config.C_GLASS_3,
            scrollbar_button_hover_color=config.C_LINE_3)
        self.scroll.pack(fill="both", expand=True)

        self.list_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True)
        self.list_container.bind("<Configure>", self._on_list_configure)
        self._configure_columns(self._cols)
        self._install_smooth_wheel()

        # 欢迎页叠层（初始隐藏，未扫描时显示）
        self.welcome_layer = ctk.CTkFrame(
            self.list_area, fg_color=config.C_BG_ALT, corner_radius=T.R.MD)
        self._welcome_inner = None

        if not self.has_scanned:
            self._show_empty_hint()

    def _scaling_factor(self):
        """当前窗口的 DPI 缩放系数（物理像素 / CTk 逻辑单位）。"""
        try:
            return max(0.7, min(2.5, ctk.ScalingTracker.get_window_scaling(self)))
        except Exception:
            return 1.0

    def _install_smooth_wheel(self):
        """v3.0.5：接管鼠标滚轮，做「高频小步 + 合并重绘」的平滑滚动。

        背景：CTkScrollableFrame 对每个滚轮事件都调用
        ``canvas.yview("scroll", -delta/6, "units")``，一次滚动一格。
        滚动区内有 ~677 个控件，Tk 每移动一次都要重算几何 —— 实测
        6.05ms/次（静止时仅 0.32ms）。高刷屏上高频滚动会迅速堆满主线程，
        表现为「页面卡顿不丝滑」。

        本实现改为：
          - 累积滚轮 delta → 换算成目标位置（粗调，削减事件数量）
          - 用 ``yview_moveto`` 直接定位（避免 units 换算的额外开销）
          - 同一帧内的多次滚轮事件合并为一次重绘（after_idle 去抖）
        """
        self._wheel_accum = 0.0
        self._wheel_job = None
        # 归属判定：bind_all 是应用级全局捕获，必须确认事件落在右侧列表子树内
        # 才处理；否则放行（返回 None 不 break），交给侧栏/对话框各自的滚动框。
        # 否则在左侧滚轮会"左右一起动"，在详情对话框里滚还会带动背后的主列表。
        def _inside_list(widget):
            try:
                roots = (self.scroll, self.list_container, self.list_area)
                w = widget
                while w is not None:
                    if w in roots:
                        return True
                    w = getattr(w, "master", None)
                return False
            except Exception:
                return False

        def on_wheel(event):
            try:
                if not _inside_list(getattr(event, "widget", None)):
                    return None
                if not self.has_scanned and not self.row_widgets:
                    return
                delta = event.delta
                if delta == 0:
                    return
                cv = self.scroll._parent_canvas
                first, last = cv.yview()
                view_frac = last - first
                if view_frac >= 1.0:
                    return                      # 内容不足一屏，无需滚动
                # delta 单位是 120 的倍数（Windows）；转为视口比例步进。
                # 0.28 让一格滚轮约滚动 1/3 屏，手感接近系统原生。
                step = (-delta / 120.0) * view_frac * 0.28
                self._wheel_accum += step
                if self._wheel_job is None:
                    self._wheel_job = self.after_idle(self._flush_wheel)
                return "break"
            except Exception:
                return None

        for w in (self.scroll, self.list_container,
                  self.scroll._parent_canvas):
            try:
                w.bind("<MouseWheel>", on_wheel, add="+")
            except Exception:
                pass
        # 卡片等子控件吃掉事件到不了滚动框自身，加全局捕获兜底；
        # 用 add="+" 追加并在回调里 break，避免覆盖 CTk 内部处理。
        # 归属由 on_wheel 开头的 _inside_list 判定，非列表区事件直接放行。
        try:
            self.bind_all("<MouseWheel>", on_wheel, add="+")
        except Exception:
            pass

    def _flush_wheel(self):
        """把累积的滚轮位移一次性应用（合并同帧内的多次滚轮事件）。

        v3.0.5：直接移动 canvas 后**手动同步滚动条**，绕开
        CTkScrollableFrame 内部 ``scrollbar.set()`` 的完整重绘路径。
        CTkScrollbar.set() → _draw() 每次都要重算缩放后的圆角路径并调
        draw_rounded_scrollbar（实测 5.4ms/次），是滚动卡顿的第二大来源。
        这里直接用 canvas 坐标更新滑块，成本 <0.1ms，视觉结果一致。
        """
        self._wheel_job = None
        try:
            accum = self._wheel_accum
            self._wheel_accum = 0.0
            if accum == 0.0:
                return
            cv = self.scroll._parent_canvas
            first, last = cv.yview()
            view_frac = last - first
            if view_frac >= 1.0:
                return
            target = first + accum
            target = max(0.0, min(1.0 - view_frac, target))
            cv.yview_moveto(target)
            self._fast_scrollbar_sync(target, view_frac)
        except Exception:
            pass

    def _fast_scrollbar_sync(self, start, view_frac):
        """轻量同步滚动条滑块位置（替代 CTkScrollbar.set 的整条重绘）。

        只更新 canvas 上现有的 scrollbar item 坐标，不重建路径、
        不重算字体字形，因此开销恒定且极小。失败时回落标准 set()。
        """
        try:
            sb = getattr(self.scroll, "_scrollbar", None)
            if sb is None:
                return
            cv = sb._canvas
            w = sb._current_width
            h = sb._current_height
            if w <= 0 or h <= 0:
                return
            sp = sb._border_spacing
            # 与 CTkScrollbar._draw 的几何一致（竖直方向）
            _, end_c = sb._get_scrollbar_values_for_minimum_pixel_size()
            y0 = start * h + sp
            y1 = min(h - sp, (start + view_frac) * h - sp)
            if y1 - y0 < 1.0:
                y1 = y0 + 1.0
            ids = cv.find_withtag("scrollbar_parts")
            if ids:
                for i in ids:
                    cv.coords(i, w - sp, y0, sp, y1)
                return
            sb.set(start, start + view_frac)
        except Exception:
            try:
                self.scroll._scrollbar.set(start, start + view_frac)
            except Exception:
                pass

    def _on_list_configure(self, event):
        """容器尺寸变化时，根据宽度重新计算列数并重排卡片。"""
        if not self.has_scanned:
            return
        width = max(200, event.width)
        factor = self._scaling_factor()
        new_cols = max(1, min(4, int(width // (330 * factor))))
        self._col_width = max(160, (width / new_cols) / factor)
        if new_cols != self._cols:
            self._cols = new_cols
            self._configure_columns(new_cols)
            self._relayout_cards()
        else:
            self._update_desc_wraplength()

    def _update_desc_wraplength(self):
        """按当前列宽更新所有卡片描述/文本的换行宽度。"""
        wrap = max(180, self._col_width - 56)
        for item in self.row_widgets:
            desc = item.get("desc_label")
            if desc is not None:
                try:
                    desc.configure(wraplength=wrap)
                except Exception:
                    pass

    def _configure_columns(self, cols):
        """设置前 cols 列等宽；多余列 weight=0 不占空间。"""
        max_cfg = max(self._max_cols_cfg, cols)
        for c in range(max_cfg):
            if c < cols:
                self.list_container.columnconfigure(c, weight=1, uniform="col")
            else:
                self.list_container.columnconfigure(c, weight=0)
        self._max_cols_cfg = max_cfg

    def _relayout_cards(self):
        """按当前列数重新 grid 所有已存在的卡片。"""
        cols = self._cols
        for idx, item in enumerate(self.row_widgets):
            card = item["card"]
            try:
                card.grid_forget()
            except Exception:
                pass
            card.grid(row=idx // cols, column=idx % cols,
                      sticky="ew", padx=6, pady=5)
        self._update_desc_wraplength()

    # ---------- 空状态 ----------
    def _hide_empty_hint(self):
        """收起欢迎叠层，恢复滚动区。"""
        try:
            self.welcome_layer.pack_forget()
        except Exception:
            pass
        try:
            self.scroll.pack(fill="both", expand=True)
        except Exception:
            pass
        self._welcome_inner = None

    def _show_empty_hint(self):
        """欢迎页：品牌区 + 三步流程卡 + 主操作按钮。

        构建在 ``welcome_layer`` 叠层上（占满整个列表可视区），
        内容用 ``place(relx=.5, rely=.5)`` 相对可视区精确居中。
        """
        # 收起滚动区，铺开欢迎叠层
        try:
            self.scroll.pack_forget()
        except Exception:
            pass
        self.welcome_layer.pack(fill="both", expand=True)

        for w in self.welcome_layer.winfo_children():
            w.destroy()

        inner = ctk.CTkFrame(self.welcome_layer, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center", y=-16)
        self._welcome_inner = inner

        # 品牌区：图标胶囊 + 光晕环（v4.3.0：底色加深，图标更醒目）
        brand = ctk.CTkFrame(inner, fg_color="transparent")
        brand.pack(pady=(0, T.SP.LG))
        ring = ctk.CTkLabel(
            brand, text="", width=84, height=84, corner_radius=42,
            fg_color=_mix_color(config.C_BG, config.C_PRIMARY, 0.18))
        ring.pack()
        icon_holder = ctk.CTkLabel(
            ring, text="", width=64, height=64, corner_radius=T.R.XL,
            fg_color=_mix_color(config.C_GLASS, config.C_PRIMARY, 0.32))
        icon_holder.place(relx=0.5, rely=0.5, anchor="center")
        img = ui_icon("empty", 34)
        if img is not None:
            icon_holder.configure(image=img)

        ctk.CTkLabel(inner, text="欢迎使用 C盘垃圾清理工具",
                     font=fnt(T.FS.DISPLAY, "bold"),
                     text_color=config.C_TEXT).pack()
        ctk.CTkLabel(
            inner,
            text="仅清理系统目录与 AppData / ProgramData 中的缓存 / 临时 / 日志\n"
                 "不会删除你的个人文档 / 桌面 / 下载 / 图片 / 视频",
            font=fnt(T.FS.BODY), text_color=config.C_TEXT_3,
            justify="center").pack(pady=(T.SP.MD, T.SP.XL))

        # 三步流程卡
        steps = ctk.CTkFrame(inner, fg_color="transparent")
        steps.pack(pady=(0, T.SP.XL))
        for idx, (icon, step_no, step_text, color) in enumerate((
            ("scan", "第一步", "点击「开始扫描」\n分析全部可清理项", config.C_PRIMARY),
            ("sel_all_off", "第二步", "勾选要清理的项目\n可按分类筛选搜索", config.C_WARN),
            ("clean", "第三步", "点击「清理选中」\n释放磁盘空间", config.C_SUCCESS),
        )):
            step = ctk.CTkFrame(steps, fg_color=config.C_GLASS,
                                corner_radius=T.R.LG, width=196, height=196)
            step.pack(side="left", padx=T.SP.SM)
            step.pack_propagate(False)
            draw_card_shell(step, fg=config.C_GLASS, radius=T.R.LG,
                            border=config.C_GLASS_BORDER)
            bind_hover(step, config.C_GLASS, config.C_GLASS_HOV)

            # 序号徽标（右上角）
            ctk.CTkLabel(step, text=f"0{idx + 1}",
                         font=fnt(T.FS.MICRO, "bold"),
                         text_color=_mix_color(config.C_GLASS, color, 0.75),
                         width=24, height=18, corner_radius=T.R.XS,
                         fg_color=_mix_color(config.C_GLASS, color, 0.16)
                         ).place(relx=0.90, rely=0.10, anchor="ne")

            ic = ctk.CTkLabel(step, text="", width=48, height=48,
                              corner_radius=T.R.MD,
                              fg_color=_mix_color(config.C_GLASS, color, 0.34))
            ic.pack(pady=(T.SP.XL, T.SP.MD))
            s_img = ui_icon(icon, 22)
            if s_img is not None:
                ic.configure(image=s_img)
            ctk.CTkLabel(step, text=step_no, font=fnt(T.FS.H3, "bold"),
                         text_color=color).pack()
            ctk.CTkLabel(step, text=step_text, font=fnt(T.FS.CAPTION),
                         text_color=config.C_TEXT_3, justify="center",
                         wraplength=164).pack(pady=(T.SP.SM, 0))

        glass_btn(inner, "开始扫描", self.start_scan, accent=config.C_PRIMARY,
                  kind="lg", icon="scan", icon_size=19, solid=True).pack()

    # ---------- 状态栏 ----------
    def _build_status_bar(self):
        """底部状态栏：自绘进度条 + 状态指示灯 + 状态文本 + 已选统计 + 百分比。"""
        sb = make_card(self.content, fg=config.C_GLASS_2, height=T.H.STATUS)
        sb.pack(fill="x", padx=T.SP.LG, pady=(0, T.SP.LG))
        sb.pack_propagate(False)

        inner = ctk.CTkFrame(sb, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=T.SP.XL, pady=T.SP.MD)

        self.progress = ProgressBar(inner, height=7, color=config.C_PRIMARY)
        self.progress.pack(fill="x")
        self._set_progress(0)

        status_row = ctk.CTkFrame(inner, fg_color="transparent")
        status_row.pack(fill="x", pady=(T.SP.SM, 0))

        self.status_dot = ctk.CTkLabel(
            status_row, text="●", font=fnt(T.FS.MICRO),
            text_color=config.C_SUCCESS, width=14)
        self.status_dot.pack(side="left")
        self.status = ctk.CTkLabel(
            status_row, text="就绪 · 点击「开始扫描」分析 C 盘垃圾",
            font=fnt(T.FS.BODY_S), text_color=config.C_TEXT_3, anchor="w")
        self.status.pack(side="left", padx=(T.SP.XS, 0), fill="x", expand=True)
        self.sel_label = ctk.CTkLabel(
            status_row, text="", font=fnt(T.FS.BODY_S),
            text_color=config.C_TEXT_4, anchor="e")
        self.sel_label.pack(side="right", padx=(T.SP.SM, 0))
        self.progress_pct = ctk.CTkLabel(
            status_row, text="0%", font=fnt(T.FS.BODY_S, "bold"),
            text_color=config.C_TEXT_4, anchor="e", width=42)
        self.progress_pct.pack(side="right")

    def _set_progress(self, value):
        """更新进度条（确定模式）并同步百分比文字。"""
        try:
            self._stop_progress_flow()
            self.progress.set(value)
            self.progress_pct.configure(text=f"{int(value * 100)}%")
        except Exception:
            pass

    def _start_progress_flow(self):
        """扫描/清理中用**自绘定时器**驱动进度条（不确定态的流动感）。

        不用 CTkProgressBar.start()：它以 50ms 固定间隔永久重绘 canvas，
        与主线程其他 after 回调抢占，高刷屏上表现为持续掉帧。
        改为 120ms 步进（视觉依然连续），完成时 _stop_progress_flow() 彻底取消。
        """
        self._stop_progress_flow()
        try:
            self.progress.set(0.0)
            self.progress_pct.configure(text="…")
        except Exception:
            pass
        self._prog_phase = 0.0

        def tick():
            try:
                if not self.scanning and not self.cleaning:
                    self._prog_job = None
                    return
                # 反复往返填充，营造"进行中"的流动感
                self._prog_phase += 0.08
                if self._prog_phase > 1.0:
                    self._prog_phase = 0.0
                v = self._prog_phase if self._prog_phase < 0.5 else 1.0 - self._prog_phase
                self.progress.set(min(0.96, 0.15 + v * 1.4))
                self._prog_job = self.after(120, tick)
            except Exception:
                self._prog_job = None

        try:
            self._prog_job = self.after(120, tick)
        except Exception:
            self._prog_job = None

    def _stop_progress_flow(self):
        """取消自绘进度流动定时器（自绘 ProgressBar 无内部动画，无需 stop）。"""
        job = getattr(self, "_prog_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            self._prog_job = None
        try:
            self.progress.stop()
        except Exception:
            pass

    def _set_status(self, text, color=None):
        """统一设置状态栏文本与指示灯颜色。"""
        color = config.C_TEXT_3 if color is None else color
        try:
            self.status.configure(text=text, text_color=color)
            self.status_dot.configure(text_color=color)
        except Exception:
            pass

    # ---------- Toast 轻量通知 ----------
    def _toast(self, text, color=None, icon="check", duration=2800):
        """右上角浮出通知气泡（扫描/清理结果等非阻塞反馈）。

        双层布局：标题（粗体白）+ 副标题/指标（语义色高亮数字）；
        图标胶囊放大到 38px，描边柔化到 0.35，整体更通透。
        文本解析：含换行按行拆分；含" · "拆为标题+指标；否则整句作标题。
        """
        try:
            color = config.C_SUCCESS if color is None else color
            tip = getattr(self, "_toast_win", None)
            if tip is not None:
                try:
                    tip.destroy()
                except Exception:
                    pass
            tip = tk.Toplevel(self)
            self._toast_win = tip
            tip.wm_overrideredirect(True)
            tip.attributes("-topmost", True)
            style_popup(tip)  # 去白边：魔术底色+透明色键，圆角外全透
            frame = ctk.CTkFrame(tip, fg_color=config.C_GLASS_2,
                                 corner_radius=T.R.MD, border_width=0)
            frame.pack()
            draw_card_shell(frame, fg=config.C_GLASS_2, radius=T.R.MD,
                            border=_mix_color(config.C_GLASS_2, color, 0.35),
                            hl_strength=0.10, shadow=False)
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(padx=18, pady=13)
            ic = ctk.CTkLabel(
                row, text="", width=38, height=38, corner_radius=T.R.MD,
                fg_color=_mix_color(config.C_GLASS_2, color, 0.28))
            ic.pack(side="left", padx=(0, T.SP.MD))
            img = ui_icon(icon, 20)
            if img is not None:
                ic.configure(image=img)
            else:
                ic.configure(text="✓", font=fnt(T.FS.H2, "bold"),
                             text_color=color)
            # ---- 文本拆分 ----
            title, sub, sub_color = text, None, config.C_TEXT_3
            if "\n" in text:
                title, sub = text.split("\n", 1)
            elif " · " in text:
                title, sub = text.split(" · ", 1)
                sub_color = color  # 指标行（如"可释放 10.70 GB"）用语义色高亮
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left")
            ctk.CTkLabel(col, text=title.strip(), font=fnt(T.FS.BODY, "bold"),
                         text_color=config.C_TEXT, anchor="w").pack(anchor="w")
            if sub and sub.strip():
                ctk.CTkLabel(col, text=sub.strip(),
                             font=fnt(T.FS.CAPTION, "bold"
                                      if sub_color == color else "normal"),
                             text_color=sub_color, anchor="w").pack(anchor="w")
            tip.update_idletasks()
            w = tip.winfo_reqwidth()
            x = self.winfo_rootx() + self.winfo_width() - w - T.SP.XXL
            y = self.winfo_rooty() + T.SP.XXL
            tip.wm_geometry(f"+{x}+{y}")
            tip.attributes("-alpha", 0.0)
            self._toast_fade(tip, 0.0, 1.0, 130)
            tip.after(duration, lambda t=tip: self._toast_fade(t, 1.0, 0.0, 170, destroy=True))
        except Exception:
            pass

    def _toast_fade(self, tip, frm, to, steps_ms, destroy=False):
        def _tick(i=0, frm=frm, to=to):
            try:
                if not tip.winfo_exists():
                    return
                t = frm + (to - frm) * min(1.0, i / 6.0)
                tip.attributes("-alpha", t)
                if i < 6:
                    tip.after(steps_ms // 6, lambda: _tick(i + 1))
                elif destroy:
                    tip.destroy()
            except Exception:
                pass
        _tick()

    # ---------- 选择逻辑 ----------
    def _set_all(self, checked):
        # 注意：checkbox.select/deselect 只改 variable 与自身绘制，
        # 不触发 command 回调 —— 必须手动同步卡片描边与 _sel_state，
        # 否则全选后卡片边框不变、切换分类后勾选状态恢复错误。
        for item in self.row_widgets:
            if checked:
                item["checkbox"].select()
            else:
                item["checkbox"].deselect()
            try:
                self._refresh_card_state(item["card"], item["checkbox"],
                                         item["variable"], item["accent"])
            except Exception:
                pass
        self._refresh_sel_buttons()

    def _refresh_sel_buttons(self):
        """全选/全不选按钮图标随全局选中状态联动，并更新已选统计。

        v3.0.5：合并调度 —— 扫描时每添加一张卡片都会调用本方法，原先每次都
        触发 2 次 CTkButton.configure + 标签更新（O(n²) 总量）。现改为把所有
        调用合并到一帧内的单次执行（after_idle），扫描结束只重算一次。
        """
        if getattr(self, "_sel_btn_job", None) is not None:
            return
        try:
            self._sel_btn_job = self.after_idle(self._do_refresh_sel_buttons)
        except Exception:
            self._do_refresh_sel_buttons()

    def _do_refresh_sel_buttons(self):
        self._sel_btn_job = None
        try:
            items = self.row_widgets
            if not items:
                self.btn_all.configure(text="全选", image=ui_icon("sel_all_off", 20))
                self.btn_none.configure(text="全不选", image=ui_icon("sel_none_off", 20))
                self.sel_label.configure(text="")
                return
            on = 0
            sel_size = 0
            for it in items:
                if it["variable"].get() == "on":
                    on += 1
                    sel_size += it["rule"].get("_size", 0)
            all_sel = on == len(items)
            self.btn_all.configure(
                text="全选",
                image=ui_icon("sel_all_on" if all_sel else "sel_all_off", 17))
            self.btn_none.configure(
                text="全不选",
                image=ui_icon("sel_none_off" if on == 0 else "sel_none_on", 17))
            if on:
                self.sel_label.configure(
                    text=f"已选 {on}/{len(items)} · {fmt_size(sel_size)}",
                    text_color=config.C_SUCCESS)
            else:
                self.sel_label.configure(text="", text_color=config.C_TEXT_4)
        except Exception:
            pass

    # ---------- 扫描（v4.2：多核并行 + 骨架屏 + 分批建卡 + 确定性进度） ----------
    def start_scan(self):
        if self.scanning or self.cleaning:
            return
        self.scanning = True
        self._cancel_requested = False   # v2.6：重置取消标志
        self._cancel_event.clear()
        self._set_controls(False)
        set_anim_busy(True)  # v4.2：忙时 hover/按钮动画降级，主线程让给建卡+滚动
        self.has_scanned = False
        self.summary_label.configure(text="扫描中…", text_color=config.C_WARN)
        self.metric_label.configure(text="—", text_color=config.C_TEXT_3)
        for w in self.list_container.winfo_children():
            w.destroy()
        self._hide_empty_hint()
        self.list_container.rowconfigure(0, weight=0)
        self.row_widgets.clear()
        self._sel_state.clear()
        self._pending_cards = []
        self._scan_done = 0
        self._scan_total = len(self.rules)
        # v4.2.1：记录规则原始顺序。并行扫描完成顺序随机（谁先扫完谁先建卡），
        # 收尾时按此顺序重排卡片，保证每次扫描结果排序一致。
        self._rule_order = {id(r): i for i, r in enumerate(self.rules)}
        self._cancel_flush_job()
        self._refresh_sel_buttons()
        self._set_status("正在扫描 C 盘垃圾文件（含第三方应用）…", config.C_PRIMARY)
        # 确定性进度（0 → 按完成规则数推进），比纯“流动条”更可感知、更不焦虑；
        # 流动动画只在首个结果回来前做极短过渡，首卡即切确定性。
        self._stop_progress_flow()
        self._set_progress(0)
        # 骨架屏：点击瞬间即有 6 张占位呼吸，界面不再“冻住”
        self._show_scan_skeleton()
        # 捕获当前可见规则集合，扫描过程中按过滤添加卡片
        self._visible_keys = {r.get("key") for r in self._visible_rules}
        self._scan_queue = queue.Queue()
        self._scan_gen += 1
        threading.Thread(target=self._scan_worker, daemon=True).start()
        self._poll_scan_queue(self._scan_gen)

    def _scan_worker(self):
        """后台线程：多核并行扫描，结果只进 queue（绝不碰 Tk）。"""
        q = self._scan_queue

        def _on_done(rule, _count, _size):
            try:
                q.put(("rule", rule))
            except Exception:
                pass

        try:
            all_count, all_size, cancelled = scan_rules_parallel(
                self.rules, cancel_check=self._cancel_event.is_set,
                on_rule_done=_on_done)
        except Exception as e:
            _logger.warning("并行扫描失败: %s", e)
            all_count, all_size, cancelled = 0, 0, False
        if self._closing:
            return
        _logger.info("扫描结束: %d 个文件 / %s（取消=%s）",
                     all_count, fmt_size(all_size), cancelled)
        try:
            q.put(("done", all_count, all_size, cancelled))
        except Exception:
            pass

    def _poll_scan_queue(self, gen):
        """主线程轮询：把后台结果取出来刷新 UI（60ms 一轮，单次最多 40 条）。"""
        try:
            if self._closing or gen != self._scan_gen:
                return
            q = self._scan_queue
            drained = 0
            while drained < 40 and q is not None:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    break
                drained += 1
                if item[0] == "rule":
                    self._on_rule_scanned(item[1])
                elif item[0] == "done":
                    _, all_count, all_size, cancelled = item
                    self._finish_scan_drain(all_count, all_size, cancelled)
                    return  # 收尾链接管，不再轮询
            if self.scanning and gen == self._scan_gen:
                try:
                    self.after(60, lambda: self._poll_scan_queue(gen))
                except Exception:
                    pass
        except Exception:
            try:
                if self.scanning and gen == self._scan_gen and not self._closing:
                    self.after(120, lambda: self._poll_scan_queue(gen))
            except Exception:
                pass

    def _on_rule_scanned(self, rule):
        """主线程：单个规则扫描完成 → 进度推进 + 排队建卡。"""
        try:
            if self._closing:
                return
            self._scan_done += 1
            total = max(1, self._scan_total)
            # 确定性进度：留 5% 给收尾建卡，避免 100% 后还在建卡的割裂感
            self._set_progress_determinate(
                min(0.95, self._scan_done / total * 0.95))
            self._set_status(
                f"正在扫描 ({self._scan_done}/{self._scan_total})：{rule.get('name', '')}",
                config.C_PRIMARY)
            if rule.get("key") in self._visible_keys:
                self._pending_cards.append(rule)
                self._schedule_flush()
        except Exception:
            pass

    def _schedule_flush(self):
        """有待建卡且无待处理任务时，约一帧后批量建卡（合并高频完成回调）。"""
        if self._flush_job is not None:
            return
        try:
            self._flush_job = self.after(50, self._flush_pending_cards)
        except Exception:
            self._flush_pending_cards()

    def _cancel_flush_job(self):
        job = self._flush_job
        self._flush_job = None
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass

    def _flush_pending_cards(self):
        """每帧最多建 6 张卡（约 <30ms 主线程占用），剩下的下一帧继续。

        原实现每完成一条规则就 after 建一张卡 → 40+ 次 layout 抖动，
        主线程被建卡淹没，滚动/进度动画全掉帧。现合并为批量帧，
        每帧预算内完成，动画与滚动始终有时间片。
        """
        self._flush_job = None
        try:
            if self._closing or not self.winfo_exists():
                self._pending_cards = []
                return
            if not self._pending_cards:
                return
            # 首批真实卡片到来即撤掉骨架屏（无缝衔接，无空白闪烁）
            self._hide_scan_skeleton()
            batch = self._pending_cards[:6]
            del self._pending_cards[:6]
            for rule in batch:
                try:
                    self._add_row(rule)
                except Exception:
                    pass
            if self._pending_cards:
                try:
                    self._flush_job = self.after(50, self._flush_pending_cards)
                except Exception:
                    pass
        except Exception:
            pass

    def _finish_scan_drain(self, all_count, all_size, cancelled):
        """扫描线程已结束：等排队卡片建完再收尾，避免“100% 后还在蹦卡片”。"""
        try:
            if self._closing:
                return
            if self._pending_cards:
                self._flush_pending_cards()
                # 若还有剩余，下一轮继续等（复用同一 flush 节奏）
                if self._pending_cards:
                    self.after(80, lambda: self._finish_scan_drain(
                        all_count, all_size, cancelled))
                    return
            self._finish_scan(all_count, all_size, cancelled)
        except Exception:
            try:
                self._finish_scan(all_count, all_size, cancelled)
            except Exception:
                pass

    # ---------- 骨架屏 ----------
    def _show_scan_skeleton(self):
        """在列表区首行铺骨架占位（grid 宿主 + 内部 pack，无 pack/grid 混用冲突）。"""
        self._hide_scan_skeleton()
        try:
            host = ctk.CTkFrame(self.list_container, fg_color="transparent")
            host.grid(row=0, column=0, columnspan=10, sticky="ew")
            _cards, bars = make_skeleton_cards(host, count=6)
            self._skeleton_host = host
            self._skeleton_stop = start_skeleton_shimmer(self, bars)
        except Exception:
            self._skeleton_host = None
            self._skeleton_stop = None

    def _hide_scan_skeleton(self):
        try:
            stop = getattr(self, "_skeleton_stop", None)
            if stop is not None:
                try:
                    stop()
                except Exception:
                    pass
                self._skeleton_stop = None
        except Exception:
            pass
        try:
            host = getattr(self, "_skeleton_host", None)
            if host is not None:
                try:
                    host.destroy()
                except Exception:
                    pass
                self._skeleton_host = None
        except Exception:
            pass

    def _set_progress_determinate(self, value):
        """确定性进度设置（先停掉流动定时器，避免两者打架）。"""
        try:
            self._stop_progress_flow()
        except Exception:
            pass
        self._set_progress(value)

    def _add_row(self, rule, selected=None):
        """构建单张清理项卡片。

        v4.0 卡片结构（高 148，SURFACE 面板，圆角 14）：
            ┌─[✓] [icon] 名称 ······················ 大小 ─┐
            │        描述文字（最多两行）                    │
            │ [分类徽章] [n 个文件][⚠] ······ [查看] [📂]    │
            └──────────────────────────────────────────────┘
        选中态：1px 强调描边（canvas 内绘制，不越界）+ 复选框，不再画左侧竖条。
        悬停：整卡统一变色（configure 级联，子控件背景跟随，无补丁色）。
        默认选中：由 rule["default_on"] 决定（安全项默认勾选，需确认项默认不勾选）；
        风险项（rule["warn"]）在底行显示 ⚠ 标识，悬停查看后果。
        """
        idx = len(self.row_widgets)
        cols = self._cols
        key = rule.get("key")
        if selected is None:
            selected = rule.get("default_on", True)
        if key in self._sel_state:
            selected = self._sel_state[key]
        var = ctk.StringVar(value="on" if selected else "off")

        accent_color, category = rule_visual(rule)

        card = make_card(self.list_container, fg=config.C_GLASS,
                         radius=T.R.LG, height=156)
        card.grid(row=idx // cols, column=idx % cols, sticky="ew",
                  padx=T.SP.XS, pady=T.SP.XS)
        card.grid_propagate(False)
        bind_hover(card, config.C_GLASS, config.C_GLASS_HOV)

        PAD = T.SP.MD   # 卡片统一内边距

        # ---- 顶行：复选框 + 图标胶囊 + 名称 ... 大小 ----
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=PAD, pady=(PAD, 0))

        cb = ctk.CTkCheckBox(
            top_row, text="", variable=var, onvalue="on", offvalue="off",
            width=22, checkbox_width=19, checkbox_height=19,
            fg_color=accent_color, hover_color=accent_color,
            corner_radius=T.R.XS, border_width=2,
            border_color=config.C_LINE_3, checkmark_color="#ffffff",
            command=lambda: self._refresh_card_state(card, cb, var, accent_color))
        cb.pack(side="left", padx=(0, T.SP.SM))

        # 图标胶囊：直接复用标签承载圆角底色（不再套一层 Frame）
        # v4.3.0：底色加深（0.22→0.30），图标存在感更强
        icon_badge = ctk.CTkLabel(
            top_row, text="", width=34, height=34,
            corner_radius=T.R.SM,
            fg_color=_mix_color(config.C_GLASS, accent_color, 0.30))
        icon_badge.pack(side="left", padx=(0, T.SP.SM))
        icon_photo = rule_icon_photo(key, 30) if key else None
        if icon_photo is not None:
            try:
                icon_badge.configure(image=icon_photo)
            except Exception:
                pass
        else:
            try:
                icon_badge.configure(text="◆", font=fnt(T.FS.H3, "bold"),
                                     text_color=accent_color)
            except Exception:
                pass

        # 真实应用图标异步加载（v4.2：共享 2 线程池，原来每张卡一个线程）
        if key:
            def _load_icon_async(k=key, badge=icon_badge):
                try:
                    png = get_app_icon(k)
                    if not png:
                        return

                    def _apply_icon(png=png):
                        try:
                            if not badge.winfo_exists():
                                return
                            photo = tk.PhotoImage(data=png)
                            if photo.width() > 30:
                                s = max(1, photo.width() // 28)
                                photo = photo.subsample(s, s)
                            badge._app_photo = photo   # 防 GC
                            badge.configure(image=photo, text="",
                                            fg_color=_mix_color(
                                                config.C_GLASS, accent_color, 0.10))
                        except Exception:
                            pass
                    try:
                        self.after(0, _apply_icon)
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                self._icon_executor.submit(_load_icon_async)
            except Exception:
                pass

        name = ctk.CTkLabel(top_row, text=rule["name"],
                            font=fnt(T.FS.H3, "bold"),
                            text_color=config.C_TEXT, anchor="w")
        name.pack(side="left", fill="x", expand=True)

        sz = ctk.CTkLabel(top_row, text=fmt_size(rule["_size"]),
                          font=fnt(T.FS.H2, "bold"),
                          text_color=accent_color, anchor="e")
        sz.pack(side="right", padx=(T.SP.SM, 0))

        # ---- 描述 ----
        desc = ctk.CTkLabel(
            card, text=rule["desc"], font=fnt(T.FS.CAPTION),
            text_color=config.C_TEXT_3, anchor="w", justify="left",
            wraplength=max(180, self._col_width - 56))
        desc.pack(fill="x", padx=PAD, pady=(T.SP.SM, 0), anchor="w")
        # ---- 底行：右对齐按钮先 pack（pack 顺序决定贴边位置）----
        BOTTOM_PAD = (T.SP.MD, PAD)
        if rule.get("type") == "deep":
            detail_btn = glass_btn(
                card, "查看归属",
                command=lambda r=rule: self._show_deep_folder_details(r),
                accent=config.C_PRIMARY, kind="sm", width=104,
                parent_bg=config.C_GLASS, icon="folder", icon_size=16)
            detail_btn.pack(side="right", padx=(0, T.SP.SM), pady=BOTTOM_PAD)
            Tooltip(detail_btn, "查看每个文件夹归属的软件")
        elif rule.get("type") == "update":
            detail_btn = glass_btn(
                card, "查看安装包",
                command=lambda r=rule: self._show_update_packages(r),
                accent=config.C_PRIMARY, kind="sm", width=112,
                parent_bg=config.C_GLASS, icon="pkg", icon_size=16)
            detail_btn.pack(side="right", padx=(0, T.SP.SM), pady=BOTTOM_PAD)
            Tooltip(detail_btn, "按软件来源查看更新安装包")

        open_path = self._get_rule_open_path(rule)
        open_btn = glass_btn(
            card, "", command=lambda p=open_path: open_in_explorer(p),
            accent=config.C_TEXT_4, kind="sm", width=32,
            parent_bg=config.C_GLASS, icon="folder", icon_size=16)
        open_btn.pack(side="right", padx=(0, T.SP.SM), pady=BOTTOM_PAD)
        Tooltip(open_btn, "在资源管理器中打开")

        cat_badge = make_badge(card, category, accent_color, height=19,
                               font_size=T.FS.MICRO, padx=8)
        cat_badge.pack(side="left", padx=(PAD, T.SP.SM), pady=BOTTOM_PAD)

        cnt = ctk.CTkLabel(
            card, text=f"{rule['_count']:,} 个文件", font=fnt(T.FS.MICRO),
            text_color=config.C_TEXT_4, anchor="w",
            image=ui_icon("file", 13), compound="left")
        cnt.pack(side="left", pady=BOTTOM_PAD)

        # 风险项：徽章化标识 + 悬停说明后果（需用户确认的项默认不勾选）。
        # v4.3.0：由纯色文字改为语义徽章，与分类徽章体系统一，更精致。
        warn_text = rule.get("warn")
        warn_lbl = None
        if warn_text:
            warn_lbl = make_badge(card, "⚠ 需确认", config.C_WARN, height=19,
                                  font_size=T.FS.MICRO, padx=8)
            warn_lbl.pack(side="left", padx=(T.SP.SM, 0), pady=BOTTOM_PAD)
            Tooltip(warn_lbl, warn_text)

        # ---- 卡片整体点击切换勾选 ----
        def toggle_sel(_e=None):
            if self.cleaning:
                return
            if var.get() == "on":
                cb.deselect()
            else:
                cb.select()
            self._refresh_card_state(card, cb, var, accent_color)

        _click_widgets = [card, top_row, icon_badge, name, desc,
                          cat_badge, cnt]
        if warn_lbl is not None:
            _click_widgets.append(warn_lbl)
        for w in _click_widgets:
            w.bind("<Button-1>", toggle_sel)
            _set_hand_cursor(w)

        self._refresh_card_state(card, cb, var, accent_color)

        self.row_widgets.append({"variable": var, "checkbox": cb, "rule": rule,
                                 "card": card, "desc_label": desc,
                                 "accent": accent_color})
        # v4.2 入场呼吸描边：按建卡顺序错开 0/28/56ms…，波浪式浮现。
        # 仅 2 次 canvas itemconfig，不走 configure 级联，单卡 <0.3ms。
        try:
            animate_card_entrance(
                card, accent_color, selected=(var.get() == "on"),
                delay=(idx % 8) * 28)
        except Exception:
            pass
        self._refresh_sel_buttons()

    def _refresh_card_state(self, card, cb, var, accent_color):
        """根据勾选状态刷新卡片（仅描边）与选择记录。

        v4.0：描边由 widgets.draw_card_shell 以内缩坐标绘制（tag=card_border），
        这里只改 outline 颜色 —— 绝不使用 CTk 的 border_width（其字形外溢
        就是「卡片彩色边缘」的根因）。选中态不再绘制左侧竖条（用户反馈小蓝条
        显杂乱），仅靠「强调色描边 + 复选框」双重编码，视觉更干净。
        """
        try:
            on = var.get() == "on"
            try:
                canvas = card._canvas
                # 清理历史版本残留的左侧竖条
                canvas.delete("sel_bar")
                # 选中：强调色描边（混 45%，醒目但不刺眼）；未选中：常驻细描边
                ec = (_mix_color(config.C_GLASS_BORDER, accent_color, 0.45)
                      if on else config.C_GLASS_BORDER)
                try:
                    canvas.itemconfig("card_border", outline=ec)
                except Exception:
                    pass
            except Exception:
                pass
            rule = next((it["rule"] for it in self.row_widgets
                         if it["card"] is card), None)
            if rule is not None and rule.get("key") is not None:
                self._sel_state[rule["key"]] = on
        except Exception:
            pass
        self._refresh_sel_buttons()

    def _get_rule_open_path(self, rule):
        """取清理项用于「在资源管理器打开」的代表路径。"""
        if rule.get("paths"):
            return rule["paths"][0]
        if rule.get("roots"):
            return rule["roots"][0]
        return ""

    # ---------- 可见规则过滤（分类 + 搜索） ----------
    def _apply_visible_rules(self):
        """按当前分类与搜索词重建列表卡片（保留勾选状态）。"""
        cat = self._current_cat
        kw = self._search_text
        rules = self.rules
        if cat:
            rules = [r for r in rules if r.get("cat") == cat]
        if kw:
            rules = [r for r in rules
                     if kw in r["name"].lower()
                     or kw in r.get("desc", "").lower()]
        self._visible_rules = rules
        self._visible_keys = {r.get("key") for r in rules}
        for w in self.list_container.winfo_children():
            w.destroy()
        self.row_widgets.clear()
        self.list_container.rowconfigure(0, weight=0)
        if not self.has_scanned:
            self._show_empty_hint()
            return
        self._hide_empty_hint()
        if not rules:
            # 当前分类/搜索下无内容（但已扫描过）
            empty = EmptyState(
                self.list_container, icon="empty",
                title="没有匹配的清理项",
                desc="换个分类，或清除搜索关键词试试")
            empty.grid(row=0, column=0, columnspan=10, pady=90)
            self._refresh_sel_buttons()
            return
        for rule in rules:
            if "_files" in rule:
                self._add_row(rule)
        self._refresh_sel_buttons()

    # ---------- 详情对话框 ----------
    def _show_deep_folder_details(self, rule):
        self._open_detail_dialog(rule, FolderDetailDialog)

    def _show_update_packages(self, rule):
        self._open_detail_dialog(rule, PackageDetailDialog)

    def _open_detail_dialog(self, rule, dialog_cls):
        """打开详情对话框；相同清理项的对话框已打开时置顶聚焦而非重复创建。"""
        key = rule.get("key", id(rule))
        existing = self._open_dialogs.get(key)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass
        dlg = dialog_cls(self, rule)
        self._open_dialogs[key] = dlg
        # 对话框关闭时自动注销
        dlg._on_closed_callback = lambda k=key: self._open_dialogs.pop(k, None)
        # 二级选择变化回调：详情关闭后同步主菜单勾选状态（v2.4.1 修复）
        dlg._on_selection_changed = lambda r=rule, d=dlg: self._sync_main_selection(r, d)

    def _sync_main_selection(self, rule, dialog):
        """
        二级详情对话框关闭后，同步主菜单对应清理项的勾选状态（v2.4.1 修复）。

        双向同步（v2.4.2 修正）：
          - 二级选择「全部取消」 -> 主菜单该项取消勾选
          - 二级选择「有选中项」 -> 主菜单该项恢复勾选
        仅当对话框确实加载了数据时才联动（无数据保持主菜单原状）。
        """
        try:
            if getattr(self, "_closing", False):
                return
            t = rule.get("type")
            if t == "deep":
                sel = rule.get("_selected_folders")
            elif t == "update":
                sel = rule.get("_selected_packages")
            else:
                return
            if sel is None:
                return
            if dialog is not None and not getattr(dialog, "all_items", []):
                return
            has_sel = bool(sel)
            key = rule.get("key")
            if key is not None:
                self._sel_state[key] = has_sel
            for item in self.row_widgets:
                if item["rule"].get("key") == key:
                    var = item["variable"]
                    cur = var.get() == "on"
                    if cur != has_sel:
                        if has_sel:
                            item["checkbox"].select()
                        else:
                            item["checkbox"].deselect()
                        try:
                            _ac, _ = rule_visual(item["rule"])
                            self._refresh_card_state(item["card"], item["checkbox"], var, _ac)
                        except Exception:
                            pass
                    break
        except Exception:
            pass

    def _on_close(self):
        """主窗口关闭：先关闭详情对话框，再销毁窗口。"""
        self._closing = True
        self._cancel_requested = True
        try:
            self._cancel_event.set()
        except Exception:
            pass
        try:
            self._cancel_flush_job()
        except Exception:
            pass
        try:
            self._hide_scan_skeleton()
        except Exception:
            pass
        try:
            set_anim_busy(False)
        except Exception:
            pass
        for dlg in list(self._open_dialogs.values()):
            try:
                dlg._on_close()
            except Exception:
                pass
        self._open_dialogs.clear()
        try:
            self._icon_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        cb = getattr(self, "_on_closed_callback", None)
        if cb is not None:
            try:
                cb()
            except Exception:
                pass
        self.destroy()

    def _sort_cards_by_rule_order(self):
        """按 rules 原始顺序重排卡片（v4.2.1：排序稳定化）。

        并行扫描是谁先完成谁先建卡，顺序每次随机；收尾时按规则定义顺序
        重排一次（复用 _relayout_cards 做 grid 重排），最终呈现永远一致。
        扫描中仍渐进展示（快），结束时一次性归位（稳）。
        """
        try:
            if not self.row_widgets:
                return
            order = getattr(self, "_rule_order", None) or {}
            self.row_widgets.sort(
                key=lambda it: order.get(id(it["rule"]), 10 ** 9))
            self._relayout_cards()
        except Exception:
            pass

    def _finish_scan(self, all_count, all_size, cancelled=False):
        if self._closing:   # 窗口已关闭：不再操作控件（v2.5.3 修复）
            return
        self.scanning = False
        self._cancel_flush_job()
        self._hide_scan_skeleton()
        try:
            set_anim_busy(False)  # 恢复完整 hover 动效
        except Exception:
            pass
        self.has_scanned = True
        self._set_controls(True)
        # v4.2.1：先按规则原始顺序重排卡片（取消/完成两条路径都稳定），再同步计数
        self._sort_cards_by_rule_order()
        self._sync_sidebar_counts()
        if cancelled:
            # v2.6：取消时保留部分结果，进度条回零，不覆盖已有卡片
            self._set_progress(0)
            self.summary_label.configure(
                text=f"{all_count:,}", text_color=config.C_WARN)
            self.metric_label.configure(
                text=fmt_size(all_size), text_color=config.C_WARN)
            self._set_status(
                f"扫描已取消：已发现 {all_count:,} 个文件，约 {fmt_size(all_size)} 可释放。",
                config.C_WARN)
            self._toast(f"扫描已取消 · 已发现 {fmt_size(all_size)}", config.C_WARN,
                        icon="cancel")
            return
        self._set_progress(1)
        self.summary_label.configure(
            text=f"{all_count:,}", text_color=config.C_SUCCESS)
        self.metric_label.configure(
            text=fmt_size(all_size), text_color=config.C_SUCCESS)
        if all_count == 0:
            self._set_status("未发现可清理的垃圾文件，C 盘很干净", config.C_SUCCESS)
            self._toast("未发现可清理的垃圾文件", config.C_SUCCESS, icon="check")
        else:
            self._set_status(
                f"扫描完成：共 {all_count:,} 个文件，约 {fmt_size(all_size)} 可释放。勾选要清理的项，点击「清理选中」。",
                config.C_SUCCESS)
            self._toast(f"扫描完成 · 可释放 {fmt_size(all_size)}", config.C_SUCCESS,
                        icon="check")

    # ---------- 清理 ----------
    def start_clean(self):
        if self.scanning or self.cleaning:
            return
        selected = [(item["variable"], item["rule"]) for item in self.row_widgets
                    if item["variable"].get() == "on"]
        if not selected:
            self._toast("请先勾选要清理的项目", config.C_WARN, icon="cancel")
            return
        # 按二级选择过滤出真正要清理的文件列表（v2.3.2）
        clean_plan = []  # [(rule, filtered_files), ...]
        total_count = 0
        total_size = 0
        for _, rule in selected:
            files = filter_files_by_selection(rule, rule["_files"])
            if not files:
                continue
            clean_plan.append((rule, files))
            total_count += len(files)
            total_size += sum(sz for _, sz in files)
        if not clean_plan:
            self._toast("所选项目下没有可清理的文件\n（若进入了二级详情，请确认已勾选具体清理项）",
                        config.C_WARN, icon="cancel")
            return
        # v2.6：确认框按回收站模式给出不同的风险提示
        recycle = bool(self.cfg.get("recycle_mode"))
        mode_note = ("删除将进入回收站，误删可从回收站恢复；\n"
                     "但空间需清空回收站后才真正释放。" if recycle
                     else "将永久删除、直接释放空间（文件不可恢复）。")
        # 需确认项：把勾选的风险项后果逐条列出，避免用户稀里糊涂删掉
        warn_lines = []
        for _, rule in selected:
            w = rule.get("warn")
            if w:
                warn_lines.append(f"· {rule['name']}：{w}")
        msg = (f"即将清理 {len(clean_plan)} 类项目，共 {total_count:,} 个文件，"
               f"约 {fmt_size(total_size)}。\n")
        if warn_lines:
            msg += "\n⚠ 以下项目清理后有影响，请确认：\n" + "\n".join(warn_lines) + "\n"
        msg += (f"\n{mode_note}\n"
                "被清理的缓存/日志/临时文件通常可自动重建；\n"
                "少数文件可能因权限不足被跳过（建议以管理员身份运行）。")
        ok = mb.askyesno("确认清理", msg)
        if not ok:
            return
        self.cleaning = True
        self._cancel_requested = False   # v2.6：重置取消标志
        self._cancel_event.clear()
        self._set_controls(False)
        try:
            set_anim_busy(True)
        except Exception:
            pass
        self._set_status("正在清理…", config.C_WARN)
        self._stop_progress_flow()
        self._set_progress(0)
        self._clean_queue = queue.Queue()
        self._clean_gen += 1
        threading.Thread(target=self._clean_worker,
                         args=(clean_plan, total_count), daemon=True).start()
        self._poll_clean_queue(self._clean_gen)

    def _clean_worker(self, clean_plan, total_count):
        recycle = bool(self.cfg.get("recycle_mode"))   # v2.6
        q = self._clean_queue
        freed = 0
        deleted = 0
        skipped = 0
        done = 0
        total_rules = len(clean_plan)
        cancelled = False
        for ri, (rule, files) in enumerate(clean_plan, 1):
            # 窗口已关闭：直接退出（v2.5.3 修复）
            if self._closing:
                return
            # v2.6：用户取消 → 停止后续清理，保留已删除结果
            if self._cancel_requested:
                cancelled = True
                break
            # 进度只进 queue（v4.2 线程安全），主线程轮询刷新
            try:
                q.put(("progress", rule.get("name", ""), ri, total_rules))
            except Exception:
                pass
            f, d, s = clean_files(files, to_recycle=recycle,
                                  cancel_check=self._cancel_event.is_set)
            freed += f
            deleted += d
            skipped += s
            done += len(files)
        _logger.info("清理结束: freed=%s deleted=%d skipped=%d cancelled=%s",
                     fmt_size(freed), deleted, skipped, cancelled)
        if self._closing:
            return
        try:
            q.put(("done", freed, deleted, skipped, total_count, cancelled))
        except Exception:
            pass

    def _poll_clean_queue(self, gen):
        """主线程轮询清理进度（v4.2 线程安全）。"""
        try:
            if self._closing or gen != self._clean_gen:
                return
            q = self._clean_queue
            drained = 0
            while drained < 40 and q is not None:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    break
                drained += 1
                if item[0] == "progress":
                    _, name, v, t = item
                    self._on_clean_progress(name, v, t)
                elif item[0] == "done":
                    _, freed, deleted, skipped, total_count, cancelled = item
                    self._finish_clean(freed, deleted, skipped,
                                       total_count, cancelled)
                    return
            if self.cleaning and gen == self._clean_gen:
                try:
                    self.after(60, lambda: self._poll_clean_queue(gen))
                except Exception:
                    pass
        except Exception:
            try:
                if self.cleaning and gen == self._clean_gen and not self._closing:
                    self.after(120, lambda: self._poll_clean_queue(gen))
            except Exception:
                pass

    def _on_clean_progress(self, name, v, t):
        """主线程：清理进度回调（状态文本 + 确定性进度条，v4.2）。"""
        try:
            self._set_status(f"正在清理 ({v}/{t})：{name}", config.C_WARN)
            self._set_progress_determinate(min(0.99, (v - 1) / max(1, t)))
        except Exception:
            pass

    def _finish_clean(self, freed, deleted, skipped, total_count, cancelled=False):
        if self._closing:   # 窗口已关闭：不再操作控件（v2.5.3 修复）
            return
        self.cleaning = False
        try:
            set_anim_busy(False)
        except Exception:
            pass
        self._set_controls(True)
        self._set_progress(1)
        if cancelled:
            # v2.6：取消清理 → 展示已释放部分，不自动重扫（避免再次全量扫描）
            msg = f"清理已取消：本次已释放 {fmt_size(freed)}（删除 {deleted} 个文件）。"
            if skipped:
                msg += f"  {skipped} 个文件未能删除。"
            self._set_status(msg, config.C_WARN)
            self.summary_label.configure(text="已取消", text_color=config.C_WARN)
            self.metric_label.configure(text=fmt_size(freed), text_color=config.C_WARN)
            self._toast(msg, config.C_WARN, icon="cancel")
            return
        msg = f"清理完成！已释放 {fmt_size(freed)}（删除 {deleted} 个文件）。"
        if skipped:
            msg += f"  {skipped} 个文件因权限不足被跳过（建议以管理员身份运行）。"
        self._set_status(msg, config.C_SUCCESS)
        self.summary_label.configure(text="已清理", text_color=config.C_SUCCESS)
        self.metric_label.configure(text=fmt_size(freed), text_color=config.C_SUCCESS)
        self._toast(f"清理完成 · 释放 {fmt_size(freed)}", config.C_SUCCESS, icon="clean")
        self.start_scan()

    def _set_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in (self.btn_scan, self.btn_clean, self.btn_all, self.btn_none,
                  self.btn_theme, self.btn_exit, self.btn_settings):
            b.configure(state=state)
        # v4.3.0：忙时一并禁用搜索框。否则扫描中输入会触发 _apply_visible_rules，
        # 把欢迎层盖到骨架屏/卡片上，扫完后列表还藏在欢迎层后面（必现 bug）。
        try:
            self.search_entry.configure(state=state)
        except Exception:
            pass
        # v2.6：取消按钮逻辑相反 —— 扫描/清理进行中可用，空闲时禁用
        try:
            self.btn_cancel.configure(state="normal" if not enabled else "disabled")
        except Exception:
            pass

    def _request_cancel(self):
        """v2.6：请求取消当前扫描/清理（协作式，最快在下一个检查点生效）。"""
        if not (self.scanning or self.cleaning):
            return
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self._cancel_event.set()
        try:
            self.btn_cancel.configure(state="disabled")
        except Exception:
            pass
        self._set_status("正在取消，请稍候…", config.C_WARN)

    def _open_settings(self):
        """打开设置对话框；已打开则置顶聚焦。"""
        dlg = self._settings_dlg
        if dlg is not None:
            try:
                if dlg.winfo_exists():
                    dlg.deiconify()
                    dlg.lift()
                    dlg.focus_force()
                    return
            except Exception:
                pass
        self._settings_dlg = SettingsDialog(self, self.cfg)
