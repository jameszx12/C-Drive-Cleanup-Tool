# -*- coding: utf-8 -*-
"""启动冒烟测试：构建主窗口并校验关键属性齐全。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import CleanerApp
app = CleanerApp()

def report():
    app.update_idletasks(); app.update()
    print("[t] 窗口尺寸:", app.winfo_width(), "x", app.winfo_height())
    ok = True
    for name in ("btn_scan", "btn_clean", "btn_cancel", "btn_all", "btn_none",
                 "btn_theme", "btn_settings", "btn_exit", "card_count",
                 "card_space", "progress", "status", "sel_label", "scroll",
                 "search_entry", "list_container", "summary_label", "metric_label"):
        has = hasattr(app, name)
        ok = ok and has
        print("[t]  %-14s %s" % (name, "OK" if has else "MISSING"))
    print("[t] 侧边栏项:", len(app._side_items))
    print("[t] 结果:", "PASS" if ok else "FAIL")
    app.after(200, app.destroy)

app.after(1800, report)
app.mainloop()
print("[t] 退出正常")
