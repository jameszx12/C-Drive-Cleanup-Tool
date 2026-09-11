# -*- coding: utf-8 -*-
"""诊断脚本：启动主窗口，自动截图，采集边框绘制方式与卡片 canvas item 信息。

用法：<python> tools/diag_run.py
输出：tools/_diag_main.png 与 stdout 诊断信息
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import customtkinter as ctk
from customtkinter.windows.widgets.core_rendering import DrawEngine

print("[diag] preferred_drawing_method =", DrawEngine.preferred_drawing_method)

from app import CleanerApp

app = CleanerApp()


def report():
    print("[diag] ---- 卡片 canvas item 诊断 ----")
    for it in app.row_widgets[:1]:
        card = it["card"]
        cv = card._canvas
        print("[diag] card size =", card.winfo_width(), card.winfo_height())
        print("[diag] canvas bg =", cv.cget("bg"))
        print("[diag] corner_radius =", card.cget("corner_radius"),
              "border_width =", card.cget("border_width"),
              "border_color =", card.cget("border_color"))
        for tag in ("border_parts", "inner_parts", "background_parts",
                    "sel_bar", "glass_fx"):
            ids = cv.find_withtag(tag)
            if ids:
                for i in ids:
                    print(f"[diag]   {tag}: id={i} type={cv.type(i)} "
                          f"coords={[round(v,1) for v in cv.coords(i)]} "
                          f"fill={cv.itemcget(i, 'fill')} "
                          f"outline={cv.itemcget(i, 'outline')} "
                          f"width={cv.itemcget(i, 'width')}")
            else:
                print(f"[diag]   {tag}: (none)")
    # 截图
    try:
        from PIL import ImageGrab
        app.update()
        x = app.winfo_rootx()
        y = app.winfo_rooty()
        w = app.winfo_width()
        h = app.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        out = os.path.join("tools", "_diag_main.png")
        img.save(out)
        print("[diag] 截图已保存:", out)
    except Exception as e:
        print("[diag] 截图失败:", e)
    app.destroy()


app.after(2200, report)
app.mainloop()
