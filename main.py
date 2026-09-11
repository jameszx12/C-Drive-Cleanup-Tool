# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 v2.7.6 —— 入口与兼容导出。

模块化拆分（2026-08-04）：
  config.py      常量 / 主题 / 路径 / 用户设置 / 日志
  rules.py       垃圾类型分类 / 清理规则构建
  engine.py      扫描 / 清理 / 二级过滤（无 GUI 依赖）
  icons.py       应用图标提取与内置图标加载
  glass.py       Windows 毛玻璃背景（iOS 风格半透明）
  particles.py   动画粒子内核（v2.7.1 起 UI 不再使用，保留供性能测试）
  widgets.py     通用 UI 部件（字体 / 颜色 / 玻璃卡片工厂）
  dialogs.py     文件夹归属 / 安装包 / 设置对话框
  app.py         主窗口 CleanerApp
本文件仅做启动入口与测试兼容导出（python main.py 与既有测试仍可正常工作）。
"""
import customtkinter as ctk  # 兼容：selftest 引用 M.ctk

from config import *                      # noqa: F401,F403 颜色/常量/配置/日志
from rules import build_rules, classify_junk_type, TYPE_COLORS  # noqa: F401
from engine import (scan_rule, clean_files, filter_files_by_selection,  # noqa: F401
                    open_in_explorer, _normcase, _parse_version)
from particles import AnimatedBackground, _detect_refresh_rate, _bg_registry  # noqa: F401
from widgets import (make_glass_card, bind_hover, fnt, mono_fnt,  # noqa: F401
                     fmt_size, rule_visual, _set_hand_cursor)
from icons import get_app_icon, extract_app_icon_png  # noqa: F401
from dialogs import FolderDetailDialog, PackageDetailDialog, SettingsDialog  # noqa: F401
from app import CleanerApp  # noqa: F401


if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()
