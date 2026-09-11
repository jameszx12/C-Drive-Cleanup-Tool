# -*- coding: utf-8 -*-
"""浅色主题截图：欢迎页 + 扫描后。强制覆盖已保存的 settings.json 偏好。

用法：
    python tools/shot_light.py [welcome|scan|both]
加 --keep 保留 settings.json 的 light 偏好（默认跑完还原）。
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KEEP = "--keep" in sys.argv

# 先把用户配置里的 theme 改成 light（临时），跑完再还原
import config
cfg_path = os.path.join(config.CONFIG_DIR, "settings.json")
backup = None
if os.path.isfile(cfg_path):
    backup = open(cfg_path, encoding="utf-8").read()
    d = json.loads(backup)
    d["theme"] = "light"
    open(cfg_path, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))

from app import CleanerApp
from PIL import ImageGrab

mode = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "both")
app = CleanerApp()


def restore():
    if backup is not None and not KEEP:
        open(cfg_path, "w", encoding="utf-8").write(backup)


def grab(tag):
    try:
        app.update_idletasks(); app.update()
        time.sleep(0.4)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = app.winfo_width(), app.winfo_height()
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        out = "tools/_v4_%s.png" % tag
        img.save(out); print("[shot]", out, img.size)
    except Exception as e:
        print("[shot] 失败:", e)


def step():
    print("theme =", config.CURRENT_THEME)
    if mode in ("welcome", "both"):
        grab("welcome_light")
    if mode in ("scan", "both"):
        app.start_scan(); app.after(15000, after_scan)
    else:
        restore(); app.after(300, app.destroy)


def after_scan():
    grab("scan_light")
    restore(); app.after(300, app.destroy)


app.after(1500, step)
app.mainloop()
