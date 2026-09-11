import os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as M

# 1) import ok
print("import OK:", M.ctk.__name__)

# 2) rules built & always-present categories present
# 注意：本沙箱未安装第三方应用，相关规则因路径不存在会被运行时过滤，
# 这是预期行为。只校验「始终存在」的类别与深度扫描引擎。
rules = M.build_rules()
keys = {r["key"] for r in rules}
must = {"win_temp", "user_temp", "recycle", "prefetch", "deep_apps"}
print("rule count:", len(rules), "present:", sorted(must & keys))
assert must <= keys, (must - keys)
assert any(r["type"] == "deep" for r in rules)

# 3) deep scan on a synthetic tree
d = tempfile.mkdtemp(prefix="deep_test_")
# 应被清理
os.makedirs(os.path.join(d, "appx", "cache")); open(os.path.join(d, "appx", "cache", "a.bin"), "wb").write(b"x"*1000)
os.makedirs(os.path.join(d, "appx", "logs"));   open(os.path.join(d, "appx", "logs", "b.log"), "wb").write(b"y"*500)
open(os.path.join(d, "appx", "stray.tmp"), "wb").write(b"z"*200)   # 垃圾扩展名
# 受保护，不应被清理
os.makedirs(os.path.join(d, "documents")); open(os.path.join(d, "documents", "keep.log"), "wb").write(b"w"*300)
os.makedirs(os.path.join(d, "node_modules")); open(os.path.join(d, "node_modules", "c.tmp"), "wb").write(b"q"*100)

rule = dict(type="deep", roots=[d])
cnt, sz, files = M.scan_rule(rule)
paths = {p for p, _ in files}
print("deep -> count=%d size=%d" % (cnt, sz))
print("files:", [os.path.relpath(p, d) for p in paths])
assert cnt == 3, cnt                       # 只应有 cache/a.bin, logs/b.log, stray.tmp
assert os.path.join(d, "documents", "keep.log") not in paths
assert os.path.join(d, "node_modules", "c.tmp") not in paths

# 4) clean deletes exactly those
freed, deleted, skipped = M.clean_files(files)
assert freed == 1700 and deleted == 3, (freed, deleted)
assert not os.path.exists(os.path.join(d, "appx", "cache", "a.bin"))

shutil.rmtree(d, ignore_errors=True)
print("SELFTEST_PASS")

# ---------- 5) 软件更新安装包扫描 ----------
import os, tempfile, shutil
d2 = tempfile.mkdtemp(prefix="upd_test_")
BIG = 2 * 1024 * 1024  # 2MB，超过阈值
SMALL = 100 * 1024     # 100KB，低于阈值应被排除

# 应纳入：update 目录下的安装包
os.makedirs(os.path.join(d2, "appx", "update"))
open(os.path.join(d2, "appx", "update", "ChromeSetup_120.0.6099.109.exe"), "wb").write(b"x" * BIG)
os.makedirs(os.path.join(d2, "appx", "download"))
open(os.path.join(d2, "appx", "download", "VSCodeSetup_1.85.0.msi"), "wb").write(b"y" * BIG)
# 文件名含关键词但不在 update 目录 → 也应纳入（关键词召回）
open(os.path.join(d2, "appx", "AdobePatch_3.5.0.7z"), "wb").write(b"")  # 扩展名不对，跳过
open(os.path.join(d2, "appx", "NVIDIA_setup_551.22_desktop.exe"), "wb").write(b"n" * BIG)

# 应排除：小文件
open(os.path.join(d2, "appx", "update", "tiny_setup_1.0.0.exe"), "wb").write(b"s" * SMALL)
# 应排除：cache 目录被剪枝
os.makedirs(os.path.join(d2, "appx", "cache"))
open(os.path.join(d2, "appx", "cache", "BigSetup_9.9.9.9.exe"), "wb").write(b"c" * BIG)

rule2 = dict(type="update", roots=[d2])
cnt2, sz2, files2 = M.scan_rule(rule2)
paths2 = {p for p, _ in files2}
names2 = {os.path.basename(p) for p in paths2}
print("update -> count=%d size=%d" % (cnt2, sz2))
print("packages:", sorted(names2))

assert cnt2 == 3, cnt2  # Chrome + VSCode + NVIDIA（关键词召回）
assert "ChromeSetup_120.0.6099.109.exe" in names2
assert "VSCodeSetup_1.85.0.msi" in names2
assert "NVIDIA_setup_551.22_desktop.exe" in names2
assert "tiny_setup_1.0.0.exe" not in names2        # 小文件被排除
assert "BigSetup_9.9.9.9.exe" not in names2         # cache 目录被剪枝
assert "AdobePatch_3.5.0.7z" not in names2          # 扩展名不在 INSTALLER_EXTENSIONS

# 版本号解析
assert M._parse_version("ChromeSetup_120.0.6099.109.exe") == "120.0.6099.109"
assert M._parse_version("VSCodeSetup_1.85.0.msi") == "1.85.0"
assert M._parse_version("no_version_here.exe") == "—"

# 分组数据结构
srcs = rule2["_update_sources"]
assert len(srcs) >= 2, len(srcs)  # update 目录 + download 目录 + appx 根目录（关键词召回）
for dp, info in srcs.items():
    assert info["count"] >= 1
    assert info["size"] >= BIG
    assert "app" in info and "packages" in info
    for pkg in info["packages"]:
        assert "name" in pkg and "version" in pkg and "size" in pkg and "path" in pkg

# 清理安装包文件
freed2, deleted2, _ = M.clean_files(files2)
assert deleted2 == 3, deleted2
assert freed2 == sz2

shutil.rmtree(d2, ignore_errors=True)
print("UPDATE_SELFTEST_PASS")

# ---------- 6) 二级选择过滤逻辑（v2.3.2） ----------
# deep 规则：_selected_folders 控制按文件夹过滤
fake_deep = {
    "type": "deep",
    "_files": [
        (r"C:\App\app1\cache\a.log", 100),
        (r"C:\App\app1\cache\b.log", 200),
        (r"C:\App\app2\temp\c.tmp", 300),
        (r"C:\App\app3\logs\d.log", 400),
    ],
}
# 未选择（None）→ 清理全部
fake_deep["_selected_folders"] = None
assert len(M.filter_files_by_selection(fake_deep, fake_deep["_files"])) == 4
# 仅选 app1\cache 与 app3\logs
fake_deep["_selected_folders"] = {r"C:\App\app1\cache", r"C:\App\app3\logs"}
got = M.filter_files_by_selection(fake_deep, fake_deep["_files"])
assert len(got) == 3, got  # a.log, b.log, d.log
assert all(r"C:\App\app1\cache" in p or r"C:\App\app3\logs" in p for p, _ in got)
# 空选择 → 清理 0 个
fake_deep["_selected_folders"] = set()
assert len(M.filter_files_by_selection(fake_deep, fake_deep["_files"])) == 0

# update 规则：_selected_packages 控制按文件路径过滤
fake_upd = {
    "type": "update",
    "_files": [
        (r"C:\Google\Update\Chrome_1.exe", 1000),
        (r"C:\Google\Update\Chrome_2.exe", 2000),
        (r"C:\Adobe\setup\patch.msi", 3000),
    ],
}
fake_upd["_selected_packages"] = None
assert len(M.filter_files_by_selection(fake_upd, fake_upd["_files"])) == 3
fake_upd["_selected_packages"] = {r"C:\Google\Update\Chrome_1.exe"}
got2 = M.filter_files_by_selection(fake_upd, fake_upd["_files"])
assert len(got2) == 1 and got2[0][0] == r"C:\Google\Update\Chrome_1.exe"
fake_upd["_selected_packages"] = set()
assert len(M.filter_files_by_selection(fake_upd, fake_upd["_files"])) == 0

# path 规则：无二级选择，原样返回
fake_path = {"type": "path", "_files": [("a", 1), ("b", 2)]}
assert len(M.filter_files_by_selection(fake_path, fake_path["_files"])) == 2

print("SELECTION_FILTER_SELFTEST_PASS")

# ---------- 7) scan_path_rule 非递归 pattern 通配符匹配（v2.5.3 回归） ----------
# 曾用 startswith(pat.replace("*","")) 做前缀匹配，导致 thumbcache_*.db 永远匹配不上
d3 = tempfile.mkdtemp(prefix="pat_test_")
for name in ("thumbcache_256.db", "thumbcache_1024.db", "iconcache_512.db"):
    open(os.path.join(d3, name), "wb").write(b"x" * 10)
rule3 = dict(type="path", paths=[d3], recursive=False, pattern="thumbcache_*.db")
cnt3, _, files3 = M.scan_rule(rule3)
names3 = {os.path.basename(p) for p, _ in files3}
print("pattern -> count=%d names=%s" % (cnt3, sorted(names3)))
assert cnt3 == 2, names3  # 只应匹配 thumbcache_*.db，不含 iconcache
assert "thumbcache_256.db" in names3 and "thumbcache_1024.db" in names3
assert "iconcache_512.db" not in names3
# pattern="*" 应匹配全部文件
rule3b = dict(type="path", paths=[d3], recursive=False, pattern="*")
cnt3b, _, _ = M.scan_rule(rule3b)
assert cnt3b == 3, cnt3b
shutil.rmtree(d3, ignore_errors=True)
print("PATTERN_MATCH_SELFTEST_PASS")


