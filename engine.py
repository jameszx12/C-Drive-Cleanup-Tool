# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · 扫描与清理引擎（无 GUI 依赖，可独立测试）。"""
import os
import re
import subprocess
import fnmatch
import ctypes
import tkinter.messagebox as mb
from ctypes import wintypes
from collections import defaultdict

from config import _logger
from rules import (classify_junk_type, JUNK_FOLDER_NAMES, JUNK_EXTENSIONS,
                   SKIP_SEGMENTS, DEEP_CAP, UPDATE_SKIP_SEGMENTS,
                   UPDATE_FOLDER_NAMES, INSTALLER_EXTENSIONS,
                   INSTALLER_NAME_KEYWORDS, INSTALLER_MIN_SIZE,
                   APP_FOLDER_NAME_MAP)

# ---------- 删除到回收站（v2.6 新增） ----------
# 用 SHFileOperationW(FOF_ALLOWUNDO) 把文件删除到回收站（可恢复），
# 替代永久 os.remove。按父目录分组批量调用以摊薄每调用开销。
_FO_DELETE = 3
_FOF_ALLOWUNDO = 0x0040      # 允许撤销 → 进回收站
_FOF_NOCONFIRMATION = 0x0010 # 不弹确认框
_FOF_SILENT = 0x0004         # 不显示进度 UI
_FOF_NOERRORUI = 0x0400      # 不显示错误 UI


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def _delete_to_recycle(paths):
    """把一组文件（同目录，<=200 个）删除到回收站。返回是否成功（整体）。"""
    if not paths:
        return True
    try:
        pfrom = "\0".join(paths) + "\0\0"
        op = _SHFILEOPSTRUCTW()
        op.wFunc = _FO_DELETE
        op.pFrom = pfrom
        op.fFlags = (_FOF_ALLOWUNDO | _FOF_NOCONFIRMATION
                     | _FOF_SILENT | _FOF_NOERRORUI)
        op.fAnyOperationsAborted = False
        ctypes.windll.shell32.SHFileOperationW.restype = ctypes.c_int
        ctypes.windll.shell32.SHFileOperationW.argtypes = [ctypes.c_void_p]
        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return res == 0
    except Exception as e:
        _logger.warning("SHFileOperationW 异常: %s", e)
        return False

# ---------- 深度扫描引擎配置 ----------

def scan_path_rule(rule, cancel_check=None):
    count = 0
    size = 0
    files = []
    for base in rule["paths"]:
        if not base or not os.path.exists(base):
            continue
        try:
            if rule["recursive"]:
                for root, dirs, fnames in os.walk(base, onerror=lambda e: None):
                    if cancel_check and cancel_check():
                        return count, size, files
                    for fn in fnames:
                        fp = os.path.join(root, fn)
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            continue
                        count += 1
                        size += sz
                        files.append((fp, sz))
            else:
                pat = rule["pattern"]
                for fn in os.listdir(base):
                    if cancel_check and cancel_check():
                        return count, size, files
                    # v2.5.3 修复：原实现用 startswith(pat.replace("*","")) 做前缀匹配，
                    # 导致 thumbcache_*.db 这类模式永远匹配不上（真实文件 thumbcache_256.db
                    # 不以 "thumbcache_.db" 开头）→ 改用标准 fnmatch 通配符匹配
                    if not fnmatch.fnmatch(fn.lower(), pat.lower()):
                        continue
                    fp = os.path.join(base, fn)
                    if os.path.isfile(fp):
                        try:
                            sz = os.path.getsize(fp)
                        except OSError:
                            continue
                        count += 1
                        size += sz
                        files.append((fp, sz))
        except (OSError, PermissionError):
            continue
    return count, size, files


def app_name_for_folder(folder, scan_root):
    """将深度扫描命中的目录归属到其 AppData/ProgramData 应用目录。"""
    try:
        relative = os.path.relpath(folder, scan_root)
    except ValueError:
        return "第三方应用（路径无法识别）"
    top_level = relative.split(os.sep, 1)[0]
    return APP_FOLDER_NAME_MAP.get(top_level.lower(), f"第三方应用（{top_level}）")


def scan_deep_rule(rule, cancel_check=None):
    count = 0
    size = 0
    files = []
    # {清理文件夹路径: {app, count, size, types(set)}}，用于在界面上说明文件夹归属与垃圾类型。
    folder_summaries = {}
    capped = False
    # 去重：跳过已被专项规则（如 nvidia 着色器缓存）覆盖的目录，
    # 否则同一文件在专项与深度清理中被计算两次（总量虚高）。
    excl = rule.get("exclude_prefixes") or []
    for root in rule["roots"]:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            if cancel_check and cancel_check():
                rule["_deep_folders"] = folder_summaries
                return count, size, files
            if excl:
                try:
                    nd = os.path.normcase(os.path.normpath(dirpath))
                except Exception:
                    nd = ""
                if any(nd == e or nd.startswith(e + os.sep) for e in excl):
                    dirnames[:] = []  # 整棵子树跳过，不再深入
                    continue
            # 剪枝：跳过受保护目录段，提升速度并保护个人数据
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_SEGMENTS]
            segs = [s.lower() for s in dirpath.split(os.sep)]
            in_junk = any(seg in JUNK_FOLDER_NAMES for seg in segs)
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                ext = os.path.splitext(fn)[1].lower()
                take = in_junk or (ext in JUNK_EXTENSIONS)
                if not take:
                    continue
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                count += 1
                size += sz
                summary = folder_summaries.setdefault(
                    dirpath,
                    {"app": app_name_for_folder(dirpath, root),
                     "count": 0, "size": 0, "types": set()},
                )
                summary["count"] += 1
                summary["size"] += sz
                # 归类垃圾类型
                summary["types"].add(classify_junk_type(segs, ext))
                if not capped:
                    files.append((fp, sz))
                    if len(files) >= DEEP_CAP:
                        capped = True
    rule["_deep_folders"] = folder_summaries
    return count, size, files


# ---------- 软件更新安装包扫描 ----------
_VERSION_RE = re.compile(r'(\d+\.\d+(?:\.\d+){1,2})')

def _parse_version(filename):
    """从文件名尝试解析版本号（匹配 x.y.z 或 x.y.z.w 形式）。"""
    m = _VERSION_RE.search(filename)
    return m.group(1) if m else "—"


def _looks_like_installer(filename):
    """文件名是否包含安装包相关关键词（用于目录名不命中时的补充召回）。"""
    fn = filename.lower()
    return any(k in fn for k in INSTALLER_NAME_KEYWORDS)


def scan_update_packages_rule(rule, cancel_check=None):
    """
    扫描软件更新安装包。

    纳入条件（同时满足）：
      1) 文件扩展名在 INSTALLER_EXTENSIONS 中
      2) 所在目录名命中 UPDATE_FOLDER_NAMES，或文件名含安装包关键词
      3) 文件大小 >= INSTALLER_MIN_SIZE（排除小工具/配置文件）
      4) 不在受保护段下（roots 仅限 AppData/ProgramData，不触及个人目录）

    产出 rule["_update_sources"]：按目录分组的安装包信息，结构同 deep 的 folder_summaries，
    但 packages 字段记录每个安装包的 文件名 / 版本 / 大小 / 路径。
    """
    count = 0
    size = 0
    files = []
    # {目录路径: {app, count, size, packages: [{name, version, size, path, ext}]}}
    sources = {}
    capped = False
    for root in rule["roots"]:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            if cancel_check and cancel_check():
                rule["_update_sources"] = sources
                return count, size, files
            # 更新安装包扫描的剪枝（比 deep 宽松，允许 download/installer 等）
            dirnames[:] = [d for d in dirnames if d.lower() not in UPDATE_SKIP_SEGMENTS]
            segs = [s.lower() for s in dirpath.split(os.sep)]
            in_update_dir = any(seg in UPDATE_FOLDER_NAMES for seg in segs)
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in INSTALLER_EXTENSIONS:
                    continue
                # 目录名不命中时，靠文件名关键词补充召回
                if not in_update_dir and not _looks_like_installer(fn):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                # 排除过小文件
                if sz < INSTALLER_MIN_SIZE:
                    continue
                count += 1
                size += sz
                summary = sources.setdefault(
                    dirpath,
                    {"app": app_name_for_folder(dirpath, root),
                     "count": 0, "size": 0, "packages": []},
                )
                summary["count"] += 1
                summary["size"] += sz
                summary["packages"].append({
                    "name": fn,
                    "version": _parse_version(fn),
                    "size": sz,
                    "path": fp,
                    "ext": ext,
                })
                if not capped:
                    files.append((fp, sz))
                    if len(files) >= DEEP_CAP:
                        capped = True
    rule["_update_sources"] = sources
    return count, size, files


def scan_rule(rule, cancel_check=None):
    t = rule.get("type")
    if t == "deep":
        return scan_deep_rule(rule, cancel_check)
    if t == "update":
        return scan_update_packages_rule(rule, cancel_check)
    return scan_path_rule(rule, cancel_check)


def clean_files(files, to_recycle=False, cancel_check=None):
    """
    清理文件列表 [(path, size), ...]。

    to_recycle=True：删除到回收站（可恢复，空间不立即释放），按父目录分组批量
    SHFileOperationW；False（默认）：永久 os.remove 直接释放空间。
    cancel_check：可选 callable，返回 True 时提前停止清理（已处理的不回退）。
    删除失败的文件路径写入日志，便于用户回溯。
    """
    freed = 0
    deleted = 0
    skipped = 0
    if to_recycle:
        # 回收站模式：按父目录分组，每批 <=200 个一次调用
        groups = defaultdict(list)
        for fp, sz in files:
            groups[os.path.dirname(fp)].append((fp, sz))
        for items in groups.values():
            if cancel_check and cancel_check():
                _logger.info("清理已取消（回收站模式），已删除 %d 个", deleted)
                break
            for i in range(0, len(items), 200):
                chunk = items[i:i + 200]
                _delete_to_recycle([fp for fp, _ in chunk])
                # 以实际存在性为准统计（SHFileOperationW 不返回逐文件结果）
                for fp, sz in chunk:
                    if not os.path.exists(fp) and not os.path.islink(fp):
                        freed += sz
                        deleted += 1
                    else:
                        skipped += 1
                        _logger.warning("回收站删除失败: %s", fp)
        return freed, deleted, skipped
    # 永久删除模式
    for fp, sz in files:
        if cancel_check and cancel_check():
            _logger.info("清理已取消（永久删除模式），已删除 %d 个", deleted)
            break
        try:
            if os.path.isfile(fp) or os.path.islink(fp):
                os.remove(fp)
                freed += sz
                deleted += 1
            else:
                skipped += 1
        except (OSError, PermissionError) as e:
            skipped += 1
            _logger.warning("删除失败: %s (%s)", fp, e)
    return freed, deleted, skipped


# ---------- 资源管理器打开（v2.3.2 新增） ----------

def open_in_explorer(path):
    """
    在 Windows 文件资源管理器中打开并定位到指定路径。
      - 路径是目录：直接打开该目录
      - 路径是文件：用 explorer /select, 定位并选中该文件
    路径不存在时弹窗提示，不抛异常。
    """
    if not path:
        mb.showwarning("提示", "该清理项没有对应的文件路径。")
        return
    # 规范化路径分隔（explorer 对正斜杠支持不佳）
    p = os.path.normpath(path)
    try:
        if os.path.isdir(p):
            # 直接打开目录
            subprocess.Popen(["explorer", p])
        elif os.path.isfile(p):
            # 定位到文件（/select, 与路径之间无空格）
            subprocess.Popen(["explorer", "/select,", p])
        else:
            # 路径不存在：尝试打开其父目录
            parent = os.path.dirname(p)
            if parent and os.path.isdir(parent):
                subprocess.Popen(["explorer", parent])
            else:
                mb.showwarning("提示", f"路径不存在或已被清理：\n{p}")
    except Exception as e:
        mb.showerror("打开失败", f"无法在资源管理器中打开：\n{p}\n\n{e}")


# ---------- 按二级选择过滤清理文件（v2.3.2 新增） ----------

def _normcase(p):
    """Windows 路径大小写归一化（比较用），避免盘符/目录大小写不一致导致漏清。"""
    try:
        return os.path.normcase(os.path.normpath(p))
    except Exception:
        return p


def filter_files_by_selection(rule, files):
    """
    根据 rule 上的二级选择状态过滤待清理文件列表。

    - deep 规则：若存在 _selected_folders（dirpath 集合），仅保留属于选中文件夹的文件；
      否则（None）清理全部（与一级勾选一致）。
    - update 规则：若存在 _selected_packages（filepath 集合），仅保留选中文件；
      否则清理全部。
    - path 规则：无二级选择，直接返回全部。
    路径比较统一按大小写归一化处理（Windows 路径不区分大小写，v2.4.3 修复）。
    """
    t = rule.get("type")
    if t == "deep":
        sel = rule.get("_selected_folders")
        if sel is None:
            return files
        sel_set = {_normcase(p) for p in sel}
        return [(fp, sz) for fp, sz in files
                if _normcase(os.path.dirname(fp)) in sel_set]
    if t == "update":
        sel = rule.get("_selected_packages")
        if sel is None:
            return files
        sel_set = {_normcase(p) for p in sel}
        return [(fp, sz) for fp, sz in files if _normcase(fp) in sel_set]
    return files
