# -*- coding: utf-8 -*-
"""回归验证 v2.4.3：双向联动 + 大小写归一化过滤。"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.argv = [os.path.join(ROOT, "main.py")]
import importlib.util
spec = importlib.util.spec_from_file_location("m", os.path.join(ROOT, "main.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# 1) 大小写归一化过滤测试
fake = {"type": "deep", "_files": [(r"C:\App\app1\cache\a.log", 100),
                                   (r"C:\App\app2\temp\b.tmp", 200)]}
fake["_selected_folders"] = {r"c:\app\app1\cache"}  # 小写，与文件大小写不同
got = m.filter_files_by_selection(fake, fake["_files"])
assert len(got) == 1 and "a.log" in got[0][0], f"大小写归一化失败: {got}"
print("1. 大小写归一化过滤 OK")

fake["_selected_folders"] = set()
assert m.filter_files_by_selection(fake, fake["_files"]) == []
print("2. 空选择 -> 0 文件 OK")

# 2) 双向联动 UI 测试
app = m.CleanerApp()
app.update_idletasks()
app.update()
rule = dict(key="deep_apps", name="第三方应用深度清理（激进）", desc="test",
            type="deep", roots=[], recursive=True, pattern="*",
            _count=5, _size=1024, _files=[])
app._add_row(rule, selected=True)
app.update_idletasks()
item = next(it for it in app.row_widgets if it["rule"]["key"] == "deep_apps")

class FakeDialog:
    all_items = [("C:\\App\\app1\\cache", {"size": 1})]
dlg = FakeDialog()

rule["_selected_folders"] = set()
app._sync_main_selection(rule, dlg)
assert item["variable"].get() == "off", "全取消应取消勾选"
print("3. 全取消 -> 取消勾选 OK")

rule["_selected_folders"] = {r"C:\App\app1\cache"}
app._sync_main_selection(rule, dlg)
assert item["variable"].get() == "on", "再全选应恢复勾选"
print("4. 再全选 -> 恢复勾选 OK")

# 3) _closing 守卫测试
app._closing = True
rule["_selected_folders"] = set()
app._sync_main_selection(rule, dlg)
assert item["variable"].get() == "on", "关闭中不应联动"
print("5. 关闭中守卫 OK")

app._on_close()
print("REGRESSION_TEST_PASS")
