# -*- coding: utf-8 -*-
"""验证打包后的 exe：manifest / 依赖清单 / 启动信号。

注意：产物带 requireAdministrator 清单，非提权进程直接 CreateProcess
会抛 WinError 740 —— 这**本身就是清单生效的证据**，不算失败。因此本脚本
分三步验证，不依赖直接启动：

  1) 文件存在 + 体积合理
  2) PE 清单里含 requireAdministrator
  3) warn-*.txt 里项目自身模块没有 missing

用法：python tools/verify_exe.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "dist", "C盘清理工具.exe")
WARN = os.path.join(ROOT, "build", "C盘清理工具", "warn-C盘清理工具.txt")

# 项目自身模块：这些若 missing 就是真问题；其余（posix/macOS/java 等）无关
OWN_MODULES = [
    "app", "config", "theme", "widgets", "dialogs", "engine", "rules", "icons",
    "main", "customtkinter", "darkdetect", "tkinter",
]


def main():
    ok = True

    if not os.path.isfile(EXE):
        print("[FAIL] 未找到 exe:", EXE)
        return 1
    size = os.path.getsize(EXE)
    print("[1/3] exe 存在，大小 %.1f MB" % (size / 1024 / 1024))
    if size < 5 * 1024 * 1024:
        print("       [WARN] 体积偏小，可能缺依赖")
        ok = False

    # ---- manifest ----
    with open(EXE, "rb") as f:
        blob = f.read()
    n_admin = blob.count(b"requireAdministrator")
    print("[2/3] requireAdministrator 出现次数 =", n_admin, "✔" if n_admin else "✘")
    if not n_admin:
        ok = False

    # ---- warn 文件 ----
    if not os.path.isfile(WARN):
        print("[3/3] [WARN] 未找到 warn 文件:", WARN)
    else:
        with open(WARN, encoding="utf-8", errors="replace") as f:
            text = f.read()
        missing = set(re.findall(r"^\s*missing module named ([A-Za-z0-9_\.]+)", text, re.M))
        base = {m.split(".")[0] for m in missing}
        hits = sorted(base & set(OWN_MODULES))
        print("[3/3] warn 里 missing 模块总数 =", len(base))
        if hits:
            print("       [FAIL] 项目模块缺失:", ", ".join(hits))
            ok = False
        else:
            print("       项目模块全部 ok（缺的都是 posix/macOS/java 等无关项）✔")

    print("=" * 46)
    print("结论:", "PASS —— 产物可发布" if ok else "FAIL —— 需排查")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
