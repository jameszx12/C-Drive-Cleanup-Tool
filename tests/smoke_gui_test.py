# -*- coding: utf-8 -*-
"""GUI smoke test."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as M

app = M.CleanerApp()
app.update_idletasks()
app.update()
print("APP_BUILD_OK")

rules = [
    dict(key="win_temp", name="Windows 临时文件", desc="C:\\Windows\\Temp 系统临时文件",
         type="path", paths=[r"C:\Windows\Temp"], recursive=True, pattern="*"),
    dict(key="deep_apps", name="第三方应用深度清理（激进）",
         desc="遍历 AppData/ProgramData 中的 cache/temp/logs 目录",
         type="deep", roots=[r"C:\Windows\Temp"], recursive=True, pattern="*"),
    dict(key="update_packages", name="软件更新安装包",
         desc="扫描各软件下载的更新安装包（.exe/.msi/.cab 等）",
         type="update", roots=[r"C:\Windows\Temp"], recursive=True, pattern="*"),
]
deep_folders = {
    r"C:\Temp\AppA\cache": {"app": "AppA", "count": 120, "size": 5 * 1024 * 1024,
                            "types": {"缓存", "临时文件"}},
    r"C:\Temp\AppB\logs": {"app": "AppB", "count": 60, "size": 2 * 1024 * 1024,
                           "types": {"日志"}},
}
upd_sources = {
    r"C:\Temp\Google\update": {"app": "Google Chrome", "count": 2, "size": 90 * 1024 * 1024,
                               "packages": [
                                   {"name": "ChromeSetup_120.0.exe", "version": "120.0",
                                    "size": 80 * 1024 * 1024,
                                    "path": r"C:\Temp\Google\update\ChromeSetup_120.0.exe",
                                    "ext": ".exe"},
                                   {"name": "tiny.msi", "version": "-", "size": 10 * 1024 * 1024,
                                    "path": r"C:\Temp\Google\update\tiny.msi", "ext": ".msi"},
                               ]},
}
rules[0].update(_count=1000, _size=12345678, _files=[])
rules[1].update(_count=180, _size=7 * 1024 * 1024, _files=[], _deep_folders=deep_folders)
rules[2].update(_count=2, _size=90 * 1024 * 1024, _files=[], _update_sources=upd_sources)

for r in rules:
    app._add_row(r)
app.update_idletasks()
app.update()
print("ADD_ROW_OK cols=", app._cols)


class E:
    width = 1500


app._on_list_configure(E)
app.update()
print("LAYOUT_WIDE_OK cols=", app._cols)
E.width = 700
app._on_list_configure(E)
app.update()
print("LAYOUT_NARROW_OK cols=", app._cols)

first = app.row_widgets[0]
before = first["variable"].get()
# CTkFrame 的 <Button-1> 绑定在内部 canvas 上（真实鼠标点击的目标）
first["card"]._canvas.event_generate("<Button-1>", x=6, y=6, when="now")
app.update()
after = first["variable"].get()
assert before != after, (before, after)
print("CARD_TOGGLE_OK", before, "->", after)

app._set_all(True)
app._set_all(False)
app._set_all(True)
app.update()
print("SET_ALL_OK")

d1 = M.FolderDetailDialog(app, rules[1])
app.update()
d2 = M.PackageDetailDialog(app, rules[2])
app.update()
d2._expand_all()
app.update()
print("DIALOGS_OK", len(d1._wrap_labels), len(d2._wrap_labels))
d1._on_close()
d2._on_close()
app.update()
print("DIALOG_CLOSE_OK")

app._toggle_theme()
app.update()
print("THEME_LIGHT_OK")
app._toggle_theme()
app.update()
print("THEME_DARK_OK")

app._on_close()
print("GUITEST_PASS")
