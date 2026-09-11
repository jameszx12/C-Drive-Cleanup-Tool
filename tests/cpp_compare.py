# -*- coding: utf-8 -*-
"""C++ 引擎 vs Python 引擎 对比验证脚本。

用法：
  python tests/cpp_compare.py                 # 对比全部规则（含 deep/update，较慢）
  python tests/cpp_compare.py --rules win_temp,user_temp,thumb
  python tests/cpp_compare.py --skip-deep     # 跳过 deep/update（最快）

输出：每规则 count/size 是否一致；文件列表排序后逐项比对（路径+大小）。
"""
import sys
import os
import json
import subprocess
import hashlib
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rules import build_rules          # noqa: E402
from engine import scan_rule           # noqa: E402

CPP_CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "cpp", "cleaner_cli.exe")
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cpp_compare")


def py_scan_one(r, with_files=True):
    res = scan_rule(r)
    out = {"key": r["key"], "cat": r.get("cat", "system"), "name": r["name"],
           "count": res[0], "size": res[1]}
    if with_files:
        out["files"] = [[fp, sz] for fp, sz in res[2]]
    # deep/update 的摘要存于 rule 内部字典（scan_rule 返回三元组）
    folders = r.get("_deep_folders")
    if r.get("type") == "deep" and folders:
        out["folders"] = [
            {"dir": d, "app": s["app"], "count": s["count"], "size": s["size"],
             "types": sorted(s["types"])}
            for d, s in sorted(folders.items())
        ]
    sources = r.get("_update_sources")
    if r.get("type") == "update" and sources:
        out["sources"] = [
            {"dir": d, "app": s["app"], "count": s["count"], "size": s["size"],
             "packages": sorted(
                 [{"name": p["name"], "version": p["version"], "size": p["size"],
                   "path": p["path"], "ext": p["ext"]} for p in s["packages"]],
                 key=lambda x: x["path"])}
            for d, s in sorted(sources.items())
        ]
    return out


def hash_files(files):
    """文件列表排序后逐项哈希（路径+大小）。"""
    h = hashlib.sha256()
    for fp, sz in sorted(files, key=lambda x: x[0]):
        h.update(fp.encode("utf-8", "replace"))
        h.update(b"\x00")
        h.update(str(sz).encode())
        h.update(b"\x00")
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="", help="逗号分隔的规则 key 白名单")
    ap.add_argument("--skip-deep", action="store_true", help="跳过 deep/update 规则")
    ap.add_argument("--json", default="", help="保存 C++ JSON 到文件")
    args = ap.parse_args()

    os.makedirs(WORK, exist_ok=True)
    cpp_json = args.json or os.path.join(WORK, "cpp_scan.json")

    rules = build_rules()
    if args.rules:
        keys = set(args.rules.split(","))
        rules = [r for r in rules if r["key"] in keys]
    if args.skip_deep:
        rules = [r for r in rules if r.get("type") in ("path",)]

    # 1) C++ 扫描（规则白名单同步传给 C++，保证两端集合严格一致）
    cmd = [CPP_CLI, "scan", "--json", cpp_json]
    if rules:
        cmd += ["--rule"] + [r["key"] for r in rules]
    print(">>", " ".join(cmd[:3]) + " ...")
    subprocess.run(cmd, check=True)
    with open(cpp_json, "r", encoding="utf-8") as f:
        cpp_data = json.load(f)

    # 2) Python 扫描
    py_data = {"rules": []}
    for r in rules:
        py_data["rules"].append(py_scan_one(r))

    # 3) 对比
    cpp_rules = {r["key"]: r for r in cpp_data["rules"]}
    py_rules = {r["key"]: r for r in py_data["rules"]}

    print(f"\n=== 规则集合对比（Python {len(py_rules)} vs C++ {len(cpp_rules)}）===")
    only_py = set(py_rules) - set(cpp_rules)
    only_cpp = set(cpp_rules) - set(py_rules)
    if only_py:
        print("  仅 Python 有:", sorted(only_py))
    if only_cpp:
        print("  仅 C++ 有:", sorted(only_cpp))
    common = sorted(set(py_rules) & set(cpp_rules))
    print(f"  共同规则: {len(common)}")

    failed = 0
    for key in common:
        pr, cr = py_rules[key], cpp_rules[key]
        issues = []
        if pr["count"] != cr["count"]:
            issues.append(f"count py={pr['count']} cpp={cr['count']}")
        if pr["size"] != cr["size"]:
            issues.append(f"size py={pr['size']} cpp={cr['size']}")
        if "files" in pr:
            h1, h2 = hash_files(pr["files"]), hash_files(cr.get("files", []))
            if h1 != h2:
                diff_detail = ""
                for a, b in zip(sorted(pr["files"], key=lambda x: x[0]),
                                sorted(cr.get("files", []), key=lambda x: x[0])):
                    if a[0] != b[0] or a[1] != b[1]:
                        diff_detail = (f"first diff: py=({a[0]},{a[1]}) "
                                       f"cpp=({b[0]},{b[1]})")
                        break
                else:
                    diff_detail = "len differs: py=%d cpp=%d" % (
                        len(pr["files"]), len(cr.get("files", [])))
                issues.append("files hash mismatch (" + diff_detail + ")")
        if "folders" in pr:
            pf = pr.get("folders", [])
            cf = cr.get("folders", [])
            if pf != cf:
                issues.append(f"folders mismatch py={len(pf)} cpp={len(cf)}")
        if "sources" in pr:
            ps = pr.get("sources", [])
            cs = cr.get("sources", [])
            if ps != cs:
                issues.append(f"sources mismatch py={len(ps)} cpp={len(cs)}")
        mark = "OK " if not issues else "FAIL"
        print(f"  [{mark}] {key:20s} count={pr['count']:8d} size={pr['size']:12d}"
              + (f"  {'; '.join(issues)}" if issues else ""))
        if issues:
            failed += 1

    tp = cpp_data.get("totals", {})
    py_total_c = sum(r["count"] for r in py_data["rules"])
    py_total_s = sum(r["size"] for r in py_data["rules"])
    print(f"\n=== 汇总 ===\n  Python: count={py_total_c} size={py_total_s}")
    print(f"  C++   : count={tp.get('count')} size={tp.get('size')}")
    print(f"\n{'ALL MATCH' if failed == 0 and not only_py and not only_cpp else 'DIFFERENCES FOUND'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
