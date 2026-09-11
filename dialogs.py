# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 v4.0 · 详情对话框（提取共享基类，消除 ~400 行重复）。

设计：
  - _BaseDetailDialog：通用面板头部 / 搜索 / 操作栏 / 滚动列表 / 分页脚
  - FolderDetailDialog：每个文件夹一行（应用名 + 类型徽章 + 大小）
  - PackageDetailDialog：每个来源可折叠卡片（含安装包列表）
  - SettingsDialog：现代分组设置（主题切换 / 回收站模式 / 日志路径）

v4.0：字号全部改走 theme.FS 令牌；卡片改用 make_card（自绘描边内缩）。
"""
import os
import tkinter as tk
import customtkinter as ctk

import config
import theme as T
from config import CONFIG_DIR, save_config
from widgets import (make_card, make_glass_card, bind_hover, fnt, mono_fnt,
                     _mix_color, fmt_size, glass_btn, ui_icon,
                     SegmentedControl)
from engine import open_in_explorer
from rules import TYPE_COLORS
from glass import apply_window_backdrop


def _fit_geometry(win, w, h, margin=40):
    """返回适配屏幕的居中几何串 ``WxH+X+Y``。

    CTk 的 ``geometry`` 接收的是**逻辑单位**，会按 DPI 缩放成物理像素；
    这里按缩放系数预估物理尺寸，确保对话框不会超出屏幕可用区域。
    """
    try:
        f = max(0.7, min(2.5, ctk.ScalingTracker.get_window_scaling(win)))
    except Exception:
        f = 1.0
    try:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    except Exception:
        sw, sh = 1920, 1080
    pw, ph = int(w * f), int(h * f)
    # 超出屏幕则按比例收缩（并以逻辑单位回算）
    if pw > sw - margin:
        w = int((sw - margin) / f)
    if ph > sh - margin:
        h = int((sh - margin) / f)
    x = max(0, (sw - int(w * f)) // 2)
    y = max(0, (sh - int(h * f)) // 2 - 20)
    return f"{w}x{h}+{x}+{y}"


class _BaseDetailDialog(ctk.CTkToplevel):
    """详情对话框通用基类：头部 + 搜索 + 操作栏 + 列表 + 分页脚。

    子类需重写：
      TITLE / SUBTITLE / ICON_KEY  —— 头部
      _load_data()                  —— 准备 all_items / filtered
      _apply_filter()               —— 搜索过滤（默认按 all/filtered 全匹配）
      _render_item(path, item)      —— 渲染单条
      _on_close_extra()             —— 关闭时额外保存（如 _selected_*）
    """

    PAGE_SIZE = 50
    BATCH = 8

    def __init__(self, parent, rule):
        super().__init__(parent)
        self.transient(parent)

        self.rule = rule
        self.all_items = []
        self.filtered = []
        self.current_page = 0
        self._render_job = None
        # 路径换行宽度自适应
        self._wrap_labels = []
        self._search_var = tk.StringVar()
        self._filter_job = None  # 搜索防抖：每敲一字全量重建太卡，合并180ms

        self._apply_backdrop()
        self._build_shell()
        self._load_data(rule)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _e: self._on_close())
        self.bind("<Configure>", self._on_win_configure, add="+")
        self.after(150, self._focus_search)

    def _apply_backdrop(self):
        """v3.0.1：对话框窗口缝隙毛玻璃（跟随主窗口 glass_mode 开关）。"""
        try:
            gm = getattr(self.master, "glass_mode", True)
            apply_window_backdrop(self, config.C_BG, gm)
            return
        except Exception:
            pass
        try:
            self.configure(fg_color=config.C_BG)
        except Exception:
            pass

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
        except Exception:
            pass

    def _on_win_configure(self, event):
        """窗口宽度变化时，更新所有路径标签的 wraplength。"""
        if event.widget is not self:
            return
        wrap = max(300, event.width - 130)
        for lbl in self._wrap_labels:
            try:
                lbl.configure(wraplength=wrap)
            except Exception:
                pass

    # ===== 子类需重写的常量 =====
    TITLE = "详情"
    SUBTITLE = ""
    ICON_KEY = "folder"
    SEARCH_PLACEHOLDER = "搜索…"

    def _build_shell(self):
        # 透明 content 层（露出毛玻璃背景）
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.content.lift()
        self._build_header()
        self._build_search_bar()
        self._build_action_bar()
        self._build_list()
        self._build_footer()

    def _build_header(self):
        header = make_card(self.content, fg=config.C_GLASS_2, height=96)
        header.pack(fill="x", padx=16, pady=(16, 8))
        header.pack_propagate(False)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=24, pady=16)

        row = ctk.CTkFrame(title_box, fg_color="transparent")
        row.pack(anchor="w")
        # 标题图标
        icon_lbl = ctk.CTkLabel(row, text="")
        icon_lbl.pack(side="left", padx=(0, 10))
        img = ui_icon(self.ICON_KEY, 26)
        if img is not None:
            icon_lbl.configure(image=img)
        title = ctk.CTkLabel(row, text=self.TITLE,
                             font=fnt(T.FS.H1, "bold"), text_color=config.C_TEXT, anchor="w")
        title.pack(side="left")

        sub = ctk.CTkLabel(
            title_box, text=self.SUBTITLE,
            font=fnt(T.FS.CAPTION), text_color=config.C_TEXT_DIM, anchor="w")
        sub.pack(anchor="w", pady=(4, 0))

        self.stat_label = ctk.CTkLabel(
            header, text="", font=fnt(T.FS.BODY, "bold"),
            text_color=config.C_SUCCESS, anchor="e")
        self.stat_label.pack(side="right", padx=24)

    def _build_search_bar(self):
        search_bar = ctk.CTkFrame(self.content, fg_color="transparent", height=44)
        search_bar.pack(fill="x", padx=16, pady=(4, 2))
        search_bar.pack_propagate(False)
        ctk.CTkLabel(search_bar, text="",
                     image=ui_icon("scan", 18) or "").pack(
            side="left", padx=(8, 4))
        self._search_var.trace_add("write", lambda *_: self._schedule_filter())
        self.search_entry = ctk.CTkEntry(
            search_bar, textvariable=self._search_var,
            placeholder_text=self.SEARCH_PLACEHOLDER,
            font=fnt(T.FS.BODY_S), height=36, fg_color=config.C_GLASS,
            border_color=config.C_GLASS_BORDER,
            text_color=config.C_TEXT, corner_radius=10)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        glass_btn(search_bar, "清除",
                  command=lambda: self._search_var.set(""),
                  accent=config.C_PANEL_SOFT, kind="dlg", width=80).pack(side="left")

    def _build_action_bar(self):
        """操作栏基类实现（全选/反选 + 已选统计），子类可在 super 之前/之后追加按钮。"""
        self.action_bar = ctk.CTkFrame(self.content, fg_color="transparent", height=40)
        self.action_bar.pack(fill="x", padx=16, pady=(0, 6))
        self.action_bar.pack_propagate(False)
        # 默认：全选 / 反选 / 已选统计
        self.select_all_btn = glass_btn(
            self.action_bar, "全选", command=lambda: self._set_all_filtered(True),
            accent=config.C_PRIMARY, kind="dlg", width=80)
        self.select_all_btn.pack(side="left", padx=(8, 8))
        self.invert_btn = glass_btn(
            self.action_bar, "反选", command=self._invert_filtered,
            accent=config.C_PANEL_SOFT, kind="dlg", width=80)
        self.invert_btn.pack(side="left")
        self.sel_label = ctk.CTkLabel(
            self.action_bar, text="", font=fnt(T.FS.BODY_S),
            text_color=config.C_SUCCESS, anchor="e")
        self.sel_label.pack(side="right", padx=(0, 10))

    def _build_list(self):
        # v3.0.2：列表区固定 C_BG 不透明，避免行卡片圆角在透明窗口下的边缘伪影
        self.list_frame = ctk.CTkScrollableFrame(
            self.content, fg_color=config.C_BG, corner_radius=0,
            scrollbar_button_color=config.C_GLASS_BORDER,
            scrollbar_button_hover_color=config.C_TEXT_FAINT)
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

    def _build_footer(self):
        footer = make_card(self.content, fg=config.C_GLASS_2, height=58)
        footer.pack(fill="x", padx=16, pady=(0, 16))
        footer.pack_propagate(False)

        self.prev_btn = glass_btn(
            footer, "上一页", command=self._prev_page,
            accent=config.C_PANEL_SOFT, kind="dlg", width=104,
            icon="prev", icon_size=18)
        self.prev_btn.pack(side="left", padx=(16, 6), pady=11)
        self.next_btn = glass_btn(
            footer, "下一页", command=self._next_page,
            accent=config.C_PANEL_SOFT, kind="dlg", width=104,
            icon="next", icon_size=18)
        self.next_btn.pack(side="left", padx=6, pady=11)
        self.page_label = ctk.CTkLabel(
            footer, text="", font=fnt(T.FS.BODY_S), text_color=config.C_TEXT_DIM)
        self.page_label.pack(side="left", padx=16, pady=12)
        self.total_size_label = ctk.CTkLabel(
            footer, text="", font=fnt(T.FS.BODY_S), text_color=config.C_TEXT_DIM)
        self.total_size_label.pack(side="right", padx=16, pady=12)
        self.close_btn = glass_btn(
            footer, "关闭", command=self._on_close,
            accent=config.C_PRIMARY, kind="dlg", width=92)
        self.close_btn.pack(side="right", padx=(6, 16), pady=11)

    # ===== 数据加载/过滤/渲染（子类重写） =====
    def _load_data(self, rule):
        """子类实现：从 rule 准备 all_items。"""
        self.all_items = []
        self._apply_filter()

    def _schedule_filter(self, *_):
        """搜索防抖：连续输入时只在停顿 180ms 后过滤重建一次。"""
        try:
            if self._filter_job is not None:
                self.after_cancel(self._filter_job)
        except Exception:
            pass
        try:
            self._filter_job = self.after(180, self._do_filter)
        except Exception:
            self._do_filter()

    def _do_filter(self):
        self._filter_job = None
        try:
            if not self.winfo_exists():
                return
            self._apply_filter()
        except Exception:
            pass

    def _apply_filter(self):
        """默认实现：按关键字做大小写不敏感匹配，子类可重写。"""
        kw = self._search_var.get().strip().lower()
        if not kw:
            self.filtered = self.all_items
        else:
            self.filtered = [(p, it) for p, it in self.all_items
                             if self._match_filter(kw, p, it)]
        self.current_page = 0
        self._render_page()

    def _match_filter(self, kw, path, item):
        """默认匹配：路径 + 应用名 + 类型。"""
        return (kw in path.lower()
                or kw in item.get("app", "").lower()
                or any(kw in t.lower() for t in item.get("types", set())))

    def _render_page(self):
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None

        for w in self.list_frame.winfo_children():
            w.destroy()
        self._wrap_labels = []

        total = len(self.filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.current_page = max(0, min(self.current_page, total_pages - 1))

        start = self.current_page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, total)

        self.page_label.configure(
            text=f"第 {self.current_page + 1} / {total_pages} 页  ·  当前显示 {start + 1}-{end} / {total}"
            if total else "无数据")
        self.prev_btn.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

        page_total_size = sum(it.get("size", 0) for _, it in self.filtered[start:end])
        self.total_size_label.configure(text=f"本页合计 {fmt_size(page_total_size)}")

        if total == 0:
            self._show_empty()
            return
        self._render_batch(self.filtered[start:end], 0)
        self._update_sel_label()

    def _show_empty(self):
        ctk.CTkLabel(self.list_frame, text=self._empty_text(),
                     font=fnt(T.FS.BODY), text_color=config.C_TEXT_DIM).pack(pady=60)
        self._update_sel_label()

    def _empty_text(self):
        return "没有匹配的项，试试更换关键字或清除筛选。"

    def _render_batch(self, items, index):
        if index >= len(items):
            self._render_job = None
            return
        end = min(index + self.BATCH, len(items))
        for i in range(index, end):
            self._render_item(*items[i])
        self._render_job = self.after(10, lambda: self._render_batch(items, end))

    def _render_item(self, path, item):
        raise NotImplementedError

    def _set_all_filtered(self, checked):
        """子类实现：对当前过滤项全选/反选。"""
        for path, _ in self.filtered:
            var = self._get_item_var(path)
            if var is not None:
                var.set(checked)
        self._update_sel_label()

    def _invert_filtered(self):
        for path, _ in self.filtered:
            var = self._get_item_var(path)
            if var is not None:
                var.set(not var.get())
        self._update_sel_label()

    def _get_item_var(self, path):
        """子类提供每个条目对应的 BooleanVar。"""
        return None

    def _update_sel_label(self):
        """子类按需重写。"""
        self.sel_label.configure(text="")

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next_page(self):
        total = len(self.filtered)
        total_pages = max(1, (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_page()

    def _on_close_extra(self):
        """子类关闭时保存选择状态。"""

    def _on_close(self):
        self._on_close_extra()
        for attr in ("_render_job", "_filter_job"):
            if getattr(self, attr, None) is not None:
                try:
                    self.after_cancel(getattr(self, attr))
                except Exception:
                    pass
                setattr(self, attr, None)
        cb = getattr(self, "_on_selection_changed", None)
        if cb is not None:
            try:
                cb()
            except Exception:
                pass
        cb = getattr(self, "_on_closed_callback", None)
        if cb is not None:
            try:
                cb()
            except Exception:
                pass
        self.destroy()


# ---------- 文件夹归属详情 ----------
class FolderDetailDialog(_BaseDetailDialog):
    TITLE = "文件夹归属详情"
    SUBTITLE = "展示每个待清理文件夹所属的软件及垃圾类型分类，便于确认后再清理"
    ICON_KEY = "folder"
    SEARCH_PLACEHOLDER = "按软件名 / 路径 / 垃圾类型筛选（如 Chrome、cache、日志）"

    def __init__(self, parent, rule):
        self._folder_vars = {}
        super().__init__(parent, rule)
        self.geometry(_fit_geometry(self, 1120, 720))
        self.minsize(940, 640)
        self.title("第三方深度清理 · 文件夹归属")

    def _load_data(self, rule):
        folders = rule.get("_deep_folders", {})
        self.all_items = sorted(folders.items(), key=lambda p: p[1]["size"], reverse=True)
        total_count = len(self.all_items)
        total_size = sum(it["size"] for _, it in self.all_items)
        prev_sel = rule.get("_selected_folders")
        for path, _ in self.all_items:
            default = (prev_sel is None) or (path in prev_sel)
            self._folder_vars[path] = tk.BooleanVar(value=bool(default))
        if total_count == 0:
            self.stat_label.configure(text="无数据", text_color=config.C_TEXT_DIM)
            self._show_empty()
            return
        self.stat_label.configure(
            text=f"共 {total_count} 个文件夹 · 合计 {fmt_size(total_size)}",
            text_color=config.C_SUCCESS)
        self._apply_filter()

    def _empty_text(self):
        return "本次扫描没有发现可清理的第三方应用文件夹。"

    def _render_item(self, path, item):
        card = make_card(self.list_frame, radius=T.R.LG)
        card.pack(fill="x", padx=6, pady=5)
        bind_hover(card, config.C_GLASS, config.C_GLASS_HOV)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 6))

        var = self._folder_vars.get(path) or tk.BooleanVar(value=True)
        self._folder_vars[path] = var
        cb = ctk.CTkCheckBox(
            top, text="", variable=var, onvalue=True, offvalue=False,
            width=24, checkbox_width=19, checkbox_height=19,
            fg_color=config.C_PRIMARY, hover_color=config.C_PRIMARY_HOV,
            corner_radius=5, command=lambda: self._update_sel_label())
        cb.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(top, text=item["app"], font=fnt(T.FS.H3, "bold"),
                     text_color=config.C_TEXT, anchor="w").pack(side="left", padx=(0, 10))

        for t in sorted(item.get("types", set())):
            color = TYPE_COLORS.get(t, config.C_TEXT_FAINT)
            ctk.CTkLabel(
                top, text=t, font=fnt(T.FS.MICRO, "bold"), text_color=color,
                fg_color=_mix_color(config.C_GLASS, color, 0.35),
                corner_radius=10, padx=9, pady=1, height=20
            ).pack(side="left", padx=(0, 6))

        glass_btn(top, "", command=lambda p=path: open_in_explorer(p),
                  accent=config.C_PANEL_SOFT, kind="sm", width=30,
                  parent_bg=config.C_GLASS, icon="folder", icon_size=18
                  ).pack(side="right", padx=(4, 0))

        ctk.CTkLabel(top, text=fmt_size(item["size"]),
                     font=fnt(T.FS.H3, "bold"), text_color=config.C_SUCCESS,
                     anchor="e").pack(side="right", padx=(8, 0))
        ctk.CTkLabel(top, text=f"{item['count']:,} 个文件",
                     font=fnt(T.FS.CAPTION), text_color=config.C_TEXT_DIM,
                     anchor="e").pack(side="right", padx=12)

        path_label = ctk.CTkLabel(card, text=path, font=mono_fnt(T.FS.CAPTION),
                                  text_color=config.C_TEXT_DIM, anchor="w",
                                  wraplength=max(300, self.winfo_width() - 130))
        path_label.pack(fill="x", padx=16, pady=(0, 12))
        self._wrap_labels.append(path_label)

    def _get_item_var(self, path):
        return self._folder_vars.get(path)

    def _update_sel_label(self):
        sel_count = sum(1 for v in self._folder_vars.values() if v.get())
        total = len(self._folder_vars)
        sel_size = sum(it["size"] for p, it in self.all_items
                       if self._folder_vars.get(p) and self._folder_vars[p].get())
        if total == 0:
            self.sel_label.configure(text="", text_color=config.C_TEXT_DIM)
            return
        self.sel_label.configure(
            text=f"已选 {sel_count}/{total} · {fmt_size(sel_size)}",
            text_color=config.C_SUCCESS if sel_count else config.C_TEXT_DIM)

    def _on_close_extra(self):
        sel = {p for p, v in self._folder_vars.items() if v.get()}
        if self.all_items:
            self.rule["_selected_folders"] = sel


# ---------- 软件更新安装包详情 ----------
class PackageDetailDialog(_BaseDetailDialog):
    TITLE = "软件更新安装包"
    SUBTITLE = "按软件来源分组，点击展开查看每个安装包的文件名 / 版本 / 大小"
    ICON_KEY = "pkg"
    SEARCH_PLACEHOLDER = "按软件名 / 文件名 / 版本筛选（如 Chrome、setup、1.2.3）"
    BATCH = 6

    def __init__(self, parent, rule):
        self._pkg_vars = {}
        self._src_vars = {}  # source_path -> header checkbox var（常驻，全选时直接同步）
        self._expanded = set()
        super().__init__(parent, rule)
        self.geometry(_fit_geometry(self, 1120, 720))
        self.minsize(940, 640)
        self.title("软件更新安装包 · 详情")

    def _build_action_bar(self):
        """PackageDetail 的操作栏：展开/收起 + 全选/反选。"""
        self.action_bar = ctk.CTkFrame(self.content, fg_color="transparent", height=40)
        self.action_bar.pack(fill="x", padx=16, pady=(0, 6))
        self.action_bar.pack_propagate(False)
        self.expand_all_btn = glass_btn(
            self.action_bar, "全部展开", command=self._expand_all,
            accent=config.C_PRIMARY, kind="dlg", width=92,
            icon="expand", icon_size=18)
        self.expand_all_btn.pack(side="left", padx=(8, 8))
        self.collapse_all_btn = glass_btn(
            self.action_bar, "全部收起", command=self._collapse_all,
            accent=config.C_PANEL_SOFT, kind="dlg", width=92,
            icon="collapse", icon_size=18)
        self.collapse_all_btn.pack(side="left", padx=(0, 8))
        ctk.CTkFrame(self.action_bar, fg_color=config.C_GLASS_BORDER, width=1).pack(
            side="left", fill="y", pady=6, padx=(0, 8))
        self.select_all_btn = glass_btn(
            self.action_bar, "全选", command=lambda: self._set_all_filtered(True),
            accent=config.C_PRIMARY, kind="dlg", width=80)
        self.select_all_btn.pack(side="left", padx=(0, 8))
        self.invert_btn = glass_btn(
            self.action_bar, "反选", command=self._invert_filtered,
            accent=config.C_PANEL_SOFT, kind="dlg", width=80)
        self.invert_btn.pack(side="left")
        self.sel_label = ctk.CTkLabel(
            self.action_bar, text="", font=fnt(T.FS.BODY_S),
            text_color=config.C_SUCCESS, anchor="e")
        self.sel_label.pack(side="right", padx=(0, 10))

    def _load_data(self, rule):
        sources = rule.get("_update_sources", {})
        self.all_items = sorted(sources.items(), key=lambda p: p[1]["size"], reverse=True)
        total_count = len(self.all_items)
        total_size = sum(it["size"] for _, it in self.all_items)
        total_pkgs = sum(it["count"] for _, it in self.all_items)
        prev_sel = rule.get("_selected_packages")
        for _, it in self.all_items:
            for pkg in it.get("packages", []):
                default = (prev_sel is None) or (pkg["path"] in prev_sel)
                self._pkg_vars[pkg["path"]] = tk.BooleanVar(value=bool(default))
        for path, it in self.all_items:
            pkgs = it.get("packages", [])
            default = ((prev_sel is None) or
                       (pkgs and all(p["path"] in prev_sel for p in pkgs)))
            self._src_vars[path] = tk.BooleanVar(value=bool(default))
        if total_count == 0:
            self.stat_label.configure(text="无数据", text_color=config.C_TEXT_DIM)
            self._show_empty()
            return
        self.stat_label.configure(
            text=f"{total_count} 个来源 · {total_pkgs} 个安装包 · {fmt_size(total_size)}",
            text_color=config.C_SUCCESS)
        self._apply_filter()

    def _match_filter(self, kw, path, item):
        if (kw in path.lower() or kw in item.get("app", "").lower()):
            return True
        return any(kw in p.get("name", "").lower()
                   or kw in p.get("version", "").lower()
                   for p in item.get("packages", []))

    def _empty_text(self):
        return "本次扫描没有发现软件更新安装包。"

    def _render_item(self, path, item):
        card = make_card(self.list_frame, radius=T.R.LG)
        card.pack(fill="x", padx=6, pady=5)
        bind_hover(card, config.C_GLASS, config.C_GLASS_HOV)

        header_row = ctk.CTkFrame(card, fg_color="transparent", cursor="hand2")
        header_row.pack(fill="x", padx=16, pady=(12, 6))

        # 表头复选框用常驻 var（而非每次渲染新建），全选/反选时直接同步，
        # 无需整页重建（原来 _render_page 会导致闪烁 + 滚回顶部）。
        src_var = self._src_vars.get(path)
        if src_var is None:
            src_var = tk.BooleanVar(value=self._is_source_all_selected(item))
            self._src_vars[path] = src_var
        src_cb = ctk.CTkCheckBox(
            header_row, text="", variable=src_var, onvalue=True, offvalue=False,
            width=24, checkbox_width=19, checkbox_height=19,
            fg_color=config.C_PRIMARY, hover_color=config.C_PRIMARY_HOV,
            corner_radius=5,
            command=lambda it=item, v=src_var: self._toggle_source(it, v))
        src_cb.pack(side="left", padx=(0, 10))

        toggle = ctk.CTkLabel(header_row, text="▶", font=fnt(T.FS.BODY_S, "bold"),
                              text_color=config.C_PRIMARY, width=16)
        toggle.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(header_row, text=item["app"], font=fnt(T.FS.H3, "bold"),
                     text_color=config.C_TEXT, anchor="w").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(header_row, text=f"{item['count']} 个安装包",
                     font=fnt(T.FS.CAPTION), text_color=config.C_TEXT_DIM,
                     anchor="w").pack(side="left", padx=(0, 10))
        glass_btn(header_row, "", command=lambda p=path: open_in_explorer(p),
                  accent=config.C_PANEL_SOFT, kind="sm", width=30,
                  parent_bg=config.C_GLASS, icon="folder", icon_size=18
                  ).pack(side="right", padx=(4, 0))
        ctk.CTkLabel(header_row, text=fmt_size(item["size"]),
                     font=fnt(T.FS.H3, "bold"), text_color=config.C_SUCCESS,
                     anchor="e").pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        path_label = ctk.CTkLabel(card, text=path, font=mono_fnt(T.FS.MICRO),
                                  text_color=config.C_TEXT_FAINT, anchor="w",
                                  wraplength=max(300, self.winfo_width() - 130))
        path_label.pack(fill="x", padx=16, pady=(0, 8))
        self._wrap_labels.append(path_label)

        for pkg in sorted(item.get("packages", []), key=lambda p: p["size"], reverse=True):
            row = ctk.CTkFrame(body, fg_color=_mix_color(config.C_GLASS, config.C_PANEL_SOFT, 0.4),
                               corner_radius=8, border_width=0)
            row.pack(fill="x", padx=12, pady=3)
            pvar = self._pkg_vars.get(pkg["path"]) or tk.BooleanVar(value=True)
            self._pkg_vars[pkg["path"]] = pvar
            pcb = ctk.CTkCheckBox(
                row, text="", variable=pvar, onvalue=True, offvalue=False,
                width=24, checkbox_width=17, checkbox_height=17,
                fg_color=config.C_PRIMARY, hover_color=config.C_PRIMARY_HOV,
                corner_radius=4,
                command=lambda it=item, v=src_var: self._sync_source_var(it, v))
            pcb.pack(side="left", padx=(10, 8), pady=6)
            ctk.CTkLabel(row, text=pkg["name"], font=fnt(T.FS.BODY_S),
                         text_color=config.C_TEXT, anchor="w").pack(side="left", padx=(0, 8))
            ver_color = config.C_PRIMARY if pkg["version"] != "—" else config.C_TEXT_FAINT
            ctk.CTkLabel(
                row, text=f"v {pkg['version']}", font=fnt(T.FS.MICRO, "bold"),
                text_color=ver_color,
                fg_color=_mix_color(config.C_GLASS, ver_color, 0.35),
                corner_radius=8, padx=8, pady=0, height=18
            ).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(row, text=pkg["ext"].lstrip(".").upper(),
                         font=fnt(T.FS.MICRO, "bold"), text_color=config.C_TEXT_DIM,
                         fg_color=config.C_GLASS_BORDER, corner_radius=6,
                         padx=6, pady=0, height=16).pack(side="left", padx=(0, 8))
            glass_btn(row, "", command=lambda p=pkg["path"]: open_in_explorer(p),
                      accent=config.C_PANEL_SOFT, kind="sm", width=30,
                      parent_bg=config.C_GLASS, icon="folder", icon_size=18
                      ).pack(side="right", padx=(10, 0), pady=4)
            ctk.CTkLabel(row, text=fmt_size(pkg["size"]),
                         font=fnt(T.FS.BODY_S, "bold"), text_color=config.C_WARN,
                         anchor="e").pack(side="right", padx=(0, 4))

        def toggle_expand(_e=None):
            if path in self._expanded:
                self._expanded.discard(path)
                body.pack_forget()
                toggle.configure(text="▶")
            else:
                self._expanded.add(path)
                body.pack(fill="x", padx=14, pady=(0, 10), after=path_label)
                toggle.configure(text="▼")

        for w in (header_row, toggle):
            w.bind("<Button-1>", toggle_expand)
        for w in (header_row, body):
            try:
                w._canvas.bind("<Button-1>", toggle_expand, add="+")
            except Exception:
                pass

        if path in self._expanded:
            body.pack(fill="x", padx=14, pady=(0, 10), after=path_label)
            toggle.configure(text="▼")

    def _is_source_all_selected(self, item):
        pkgs = item.get("packages", [])
        if not pkgs:
            return False
        return all(self._pkg_vars.get(p["path"]) and self._pkg_vars[p["path"]].get()
                   for p in pkgs)

    def _toggle_source(self, item, src_var):
        val = src_var.get()
        for p in item.get("packages", []):
            v = self._pkg_vars.get(p["path"])
            if v is not None:
                v.set(val)
        self._update_sel_label()

    def _sync_source_var(self, item, src_var):
        src_var.set(self._is_source_all_selected(item))
        self._update_sel_label()

    def _set_all_filtered(self, checked):
        for path, it in self.filtered:
            for p in it.get("packages", []):
                v = self._pkg_vars.get(p["path"])
                if v is not None:
                    v.set(checked)
            sv = self._src_vars.get(path)
            if sv is not None:
                sv.set(checked)
        self._update_sel_label()

    def _invert_filtered(self):
        for path, it in self.filtered:
            for p in it.get("packages", []):
                v = self._pkg_vars.get(p["path"])
                if v is not None:
                    v.set(not v.get())
            sv = self._src_vars.get(path)
            if sv is not None:
                sv.set(self._is_source_all_selected(it))
        self._update_sel_label()

    def _update_sel_label(self):
        sel_count = sum(1 for v in self._pkg_vars.values() if v.get())
        total = len(self._pkg_vars)
        sel_size = 0
        for _, it in self.all_items:
            for p in it.get("packages", []):
                v = self._pkg_vars.get(p["path"])
                if v and v.get():
                    sel_size += p["size"]
        if total == 0:
            self.sel_label.configure(text="", text_color=config.C_TEXT_DIM)
            return
        self.sel_label.configure(
            text=f"已选 {sel_count}/{total} · {fmt_size(sel_size)}",
            text_color=config.C_SUCCESS if sel_count else config.C_TEXT_DIM)

    def _expand_all(self):
        start = self.current_page * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, len(self.filtered))
        for path, _ in self.filtered[start:end]:
            self._expanded.add(path)
        self._render_page()

    def _collapse_all(self):
        self._expanded.clear()
        self._render_page()

    def _on_close_extra(self):
        sel = {p for p, v in self._pkg_vars.items() if v.get()}
        if self._pkg_vars:
            self.rule["_selected_packages"] = sel


# ---------- 设置对话框（v3.0 现代化分组卡片） ----------
class SettingsDialog(ctk.CTkToplevel):
    """设置：界面主题、删除到回收站（可恢复）、日志与配置目录。

    v4.0：
      - 移除「窗口毛玻璃」选项（该方案已废弃，默认关闭）。
      - 主题切换改用 SegmentedControl（胶囊滑动选中块）。
      - 卡片统一圆角 / 内距 / 字号令牌。
    """

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.title("设置")
        # 逻辑尺寸 560×620；高 DPI 下 CTk 会自动放大物理像素并夹在屏幕内。
        self.geometry(_fit_geometry(self, 560, 620))
        self.resizable(False, False)
        self.transient(parent)
        self.cfg = cfg

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self.content.lift()

        # 顶部标题栏（固定）
        header = make_card(self.content, fg=config.C_GLASS_2,
                           radius=T.R.LG, height=76)
        header.pack(fill="x", padx=T.SP.LG, pady=(T.SP.LG, T.SP.SM))
        header.pack_propagate(False)
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(side="left", padx=T.SP.XL, pady=T.SP.LG)
        icon_lbl = ctk.CTkLabel(title_row, text="")
        icon_lbl.pack(side="left", padx=(0, T.SP.MD))
        img = ui_icon("settings", 24)
        if img is not None:
            icon_lbl.configure(image=img)
        ctk.CTkLabel(title_row, text="设置", font=fnt(T.FS.H2, "bold"),
                     text_color=config.C_TEXT).pack(side="left")

        # 选项区（可滚动，内容多也不会被裁剪）
        self._scroll = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=config.C_GLASS_3,
            scrollbar_button_hover_color=config.C_LINE_3)
        self._scroll.pack(fill="both", expand=True, padx=T.SP.SM,
                          pady=(0, T.SP.XS))
        self._cards_host = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._cards_host.pack(fill="x", expand=True)

        self._build_theme_card()
        self._build_recycle_card()
        self._build_info_card()

        # 底部按钮（固定）
        footer = ctk.CTkFrame(self.content, fg_color="transparent")
        footer.pack(fill="x", padx=T.SP.LG, pady=(T.SP.SM, T.SP.LG))
        glass_btn(footer, "保存", command=self._save,
                  accent=config.C_PRIMARY, kind="dlg", width=100).pack(
            side="right")
        glass_btn(footer, "取消", command=self._close,
                  accent=config.C_GLASS_3, kind="dlg", width=92).pack(
            side="right", padx=(0, T.SP.SM))

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _e: self._close())

    # ---------- 卡片骨架 ----------
    def _card(self, icon_name, title):
        """统一卡片：图标 + 标题 + 返回内容容器。"""
        card = make_card(self._cards_host, radius=T.R.LG)
        card.pack(fill="x", padx=T.SP.MD, pady=T.SP.SM)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=T.SP.XL, pady=(T.SP.LG, T.SP.SM))
        if icon_name:
            icon = ctk.CTkLabel(head, text="")
            icon.pack(side="left", padx=(0, T.SP.SM))
            img = ui_icon(icon_name, 19)
            if img is not None:
                icon.configure(image=img)
        ctk.CTkLabel(head, text=title, font=fnt(T.FS.BODY, "bold"),
                     text_color=config.C_TEXT).pack(side="left")
        return card

    # ---------- 主题 ----------
    def _build_theme_card(self):
        card = self._card("moon", "界面主题")
        cur = self.cfg.get("theme", "dark")
        self._theme_var = tk.StringVar(value=cur)
        self._theme_seg = SegmentedControl(
            card,
            [("light", "浅色"), ("auto", "跟随系统"), ("dark", "深色")],
            command=self._select_theme, accent=config.C_PRIMARY,
            height=38, width=468)
        self._theme_seg.pack(anchor="w", padx=T.SP.XL, pady=(0, T.SP.LG))
        try:
            self._theme_seg.set(cur)
        except Exception:
            pass

    def _select_theme(self, val):
        self._theme_var.set(val)

    # ---------- 回收站 ----------
    def _build_recycle_card(self):
        card = self._card("check", "删除到回收站")
        self.recycle_var = tk.BooleanVar(value=bool(self.cfg.get("recycle_mode")))
        cb = ctk.CTkCheckBox(
            card, text="开启（误删可从回收站恢复）", variable=self.recycle_var,
            font=fnt(T.FS.BODY), text_color=config.C_TEXT,
            fg_color=config.C_SUCCESS, hover_color=config.C_SUCCESS,
            corner_radius=T.R.XS, checkbox_width=20, checkbox_height=20,
            border_width=2, border_color=config.C_LINE_3,
            checkmark_color="#ffffff")
        cb.pack(anchor="w", padx=T.SP.XL, pady=(0, T.SP.SM))
        ctk.CTkLabel(
            card,
            text=("开启后，清理的文件会先进入回收站，误删可恢复；\n"
                  "但空间需清空回收站后才真正释放。\n"
                  "关闭则永久删除、直接释放空间。"),
            font=fnt(T.FS.CAPTION), text_color=config.C_TEXT_3,
            justify="left", anchor="w"
        ).pack(anchor="w", padx=T.SP.XL, pady=(0, T.SP.LG))

    # ---------- 日志目录 ----------
    def _build_info_card(self):
        card = self._card("safe", "日志与配置目录")
        ctk.CTkLabel(
            card,
            text=f"{CONFIG_DIR}\n清理失败的明细会记录在 cleaner.log 中，便于排查。",
            font=mono_fnt(T.FS.MICRO), text_color=config.C_TEXT_3,
            justify="left", anchor="w"
        ).pack(anchor="w", padx=T.SP.XL, pady=(0, T.SP.LG))

    def _save(self):
        self.cfg["recycle_mode"] = bool(self.recycle_var.get())
        new_theme = self._theme_var.get() if hasattr(self, "_theme_var") else None
        if new_theme:
            self.cfg["theme"] = new_theme
        save_config(self.cfg)
        # 主题改动即时生效（原来只存配置、重启才换肤）；扫描/清理中则仅保存。
        if new_theme and new_theme != getattr(self.master, "theme_pref", new_theme):
            try:
                self.master.apply_theme_pref(new_theme)
            except Exception:
                pass
        self._close()

    def _close(self):
        self.destroy()
