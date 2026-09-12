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
import concurrent.futures

# ---------- 多核配置（v4.2 新增） ----------
# 扫描是 IO 密集型（大量 stat/getsize 系统调用，GIL 在 syscall 时释放），
# 用线程池即可吃满多核 IO 并发；进程池反而有打包/序列化负担，GUI 程序不适用。
# 16 逻辑核心机器上实测：32 条 path 规则并行扫描可提速 3-6 倍（SSD 更明显）。
try:
    _CPU = max(1, (os.cpu_count() or 8))
except Exception:
    _CPU = 8
SCAN_WORKERS = max(4, min(16, _CPU))       # 扫描并发（path 类规则全并行）
CLEAN_WORKERS = max(4, min(8, _CPU))       # 清理并发（永久删除模式）
DEEP_SCAN_WORKERS = max(2, min(6, _CPU // 2))  # deep/update 大目录遍历的内部并发

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

# ---------- 快速遍历内核（v4.2 新增） ----------
# 原实现：os.walk + 每文件一次 os.path.getsize() —— 每次 getsize 都是一次
# 独立 stat 系统调用 + 路径拼接，在数十万文件时 syscall 开销占主导。
# 新实现：os.scandir 的 DirEntry 自带缓存 stat，一次遍历同时拿到
# is_file/is_dir/size，syscall 减半；栈式迭代避免 os.walk 的额外开销。

def _entry_size(entry):
    """取 DirEntry 文件大小；失败返回 None（无权限/竞态删除）。"""
    try:
        return entry.stat(follow_symlinks=False).st_size
    except OSError:
        return None


def _scandir_safe(path):
    """scandir 失败（无权限/已删除）时返回空迭代器而非抛异常。"""
    try:
        return os.scandir(path)
    except (OSError, PermissionError):
        return None


def scan_path_rule(rule, cancel_check=None):
    count = 0
    size = 0
    files = []
    for base in rule["paths"]:
        if not base or not os.path.exists(base):
            continue
        try:
            if rule["recursive"]:
                # 栈式 scandir 遍历：DirEntry 一次拿到类型+大小，省一半 syscall
                stack = [base]
                while stack:
                    if cancel_check and cancel_check():
                        return count, size, files
                    cur = stack.pop()
                    it = _scandir_safe(cur)
                    if it is None:
                        continue
                    try:
                        for entry in it:
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    stack.append(entry.path)
                                elif entry.is_file(follow_symlinks=False):
                                    sz = _entry_size(entry)
                                    if sz is None:
                                        continue
                                    count += 1
                                    size += sz
                                    files.append((entry.path, sz))
                            except OSError:
                                continue
                    finally:
                        try:
                            it.close()
                        except Exception:
                            pass
            else:
                pat = rule["pattern"]
                pat_low = pat.lower()
                it = _scandir_safe(base)
                if it is None:
                    continue
                try:
                    for entry in it:
                        if cancel_check and cancel_check():
                            return count, size, files
                        try:
                            if not fnmatch.fnmatch(entry.name.lower(), pat_low):
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            sz = _entry_size(entry)
                            if sz is None:
                                continue
                            count += 1
                            size += sz
                            files.append((entry.path, sz))
                        except OSError:
                            continue
                finally:
                    try:
                        it.close()
                    except Exception:
                        pass
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
        # 栈式遍历（替代 os.walk）：剪枝直接不入栈，省掉整棵子树遍历
        stack = [root]
        while stack:
            if cancel_check and cancel_check():
                rule["_deep_folders"] = folder_summaries
                return count, size, files
            dirpath = stack.pop()
            try:
                nd = os.path.normcase(os.path.normpath(dirpath))
            except Exception:
                nd = ""
            if excl and any(nd == e or nd.startswith(e + os.sep) for e in excl):
                continue  # 整棵子树跳过，不再深入
            it = _scandir_safe(dirpath)
            if it is None:
                continue
            try:
                # 先收集本层条目：目录入栈（剪枝后），文件即时判定
                subdirs = []
                filenames = []  # [(name, size or None)]
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() not in SKIP_SEGMENTS:
                                subdirs.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            filenames.append(entry)
                    except OSError:
                        continue
            finally:
                try:
                    it.close()
                except Exception:
                    pass
            # 后进先出，保持与 os.walk 相近的遍历顺序
            stack.extend(reversed(subdirs))
            segs = [s.lower() for s in dirpath.split(os.sep)]
            in_junk = any(seg in JUNK_FOLDER_NAMES for seg in segs)
            for entry in filenames:
                ext = os.path.splitext(entry.name)[1].lower()
                take = in_junk or (ext in JUNK_EXTENSIONS)
                if not take:
                    continue
                sz = _entry_size(entry)
                if sz is None:
                    continue
                fp = entry.path
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
        stack = [root]
        while stack:
            if cancel_check and cancel_check():
                rule["_update_sources"] = sources
                return count, size, files
            dirpath = stack.pop()
            it = _scandir_safe(dirpath)
            if it is None:
                continue
            try:
                subdirs = []
                file_entries = []
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # 更新安装包扫描的剪枝（比 deep 宽松，允许 download/installer 等）
                            if entry.name.lower() not in UPDATE_SKIP_SEGMENTS:
                                subdirs.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            file_entries.append(entry)
                    except OSError:
                        continue
            finally:
                try:
                    it.close()
                except Exception:
                    pass
            stack.extend(reversed(subdirs))
            # 更新安装包扫描的剪枝（比 deep 宽松，允许 download/installer 等）
            segs = [s.lower() for s in dirpath.split(os.sep)]
            in_update_dir = any(seg in UPDATE_FOLDER_NAMES for seg in segs)
            for entry in file_entries:
                fn = entry.name
                ext = os.path.splitext(fn)[1].lower()
                if ext not in INSTALLER_EXTENSIONS:
                    continue
                # 目录名不命中时，靠文件名关键词补充召回
                if not in_update_dir and not _looks_like_installer(fn):
                    continue
                sz = _entry_size(entry)
                if sz is None:
                    continue
                # 排除过小文件
                if sz < INSTALLER_MIN_SIZE:
                    continue
                fp = entry.path
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


def scan_rules_parallel(rules, cancel_check=None, on_rule_done=None,
                        max_workers=None):
    """多核并行扫描一组规则（v4.2 新增，“多调用系统核心”）。

    每个 rule 独立跑 scan_rule（线程安全：只写自己的 _count/_size/_files）。
    完成一个即回调 on_rule_done(rule, count, size)，调用方可增量刷新 UI。
    返回 (all_count, all_size, cancelled)。

    注意：deep/update 两个大遍历与 path 小规则共享线程池；在 SSD 上并行
    收益最大，HDD 上受磁盘寻道限制仍比串行快（小规则不再被大遍历阻塞）。
    """
    if not rules:
        return 0, 0, False
    workers = max_workers or min(SCAN_WORKERS, len(rules))
    workers = max(1, workers)
    all_count = 0
    all_size = 0
    cancelled = False
    import threading as _th
    lock = _th.Lock()

    def _one(rule):
        if cancel_check and cancel_check():
            return rule, 0, 0, True, True
        count, size, files = scan_rule(rule, cancel_check=cancel_check)
        rule["_count"] = count
        rule["_size"] = size
        rule["_files"] = files
        rule["_selected_folders"] = None
        rule["_selected_packages"] = None
        return rule, count, size, False, bool(cancel_check and cancel_check())

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, r): r for r in rules}
        for fut in concurrent.futures.as_completed(futs):
            try:
                rule, count, size, was_cancelled, now_cancelled = fut.result()
            except Exception as e:
                _logger.warning("并行扫描异常: %s", e)
                continue
            if was_cancelled:
                cancelled = True
                continue
            with lock:
                all_count += count
                all_size += size
                if now_cancelled:
                    cancelled = True
            if on_rule_done is not None:
                try:
                    on_rule_done(rule, count, size)
                except Exception:
                    pass
            if cancel_check and cancel_check():
                cancelled = True
                # 取消：不再等待慢任务，快速收尾（已提交的任务会自然结束）
                for f in futs:
                    f.cancel()
                break
    return all_count, all_size, cancelled


def _delete_one(args):
    """单文件删除工作函数（线程池用）：返回 (freed, deleted, skipped)。"""
    fp, sz = args
    try:
        if os.path.isfile(fp) or os.path.islink(fp):
            os.remove(fp)
            return sz, 1, 0, None
        return 0, 0, 1, None
    except (OSError, PermissionError) as e:
        return 0, 0, 1, (fp, str(e))


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
    # 永久删除模式（v4.2：多线程并行删除，IO 密集吃满多核）
    # 小批量（<500 文件）沿用串行，避免线程池启动开销反而更慢。
    if len(files) < 500:
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
    # 大批量：分块并行（每块约 500 个，块数 = workers*4，上限 64 块）
    n_chunks = max(CLEAN_WORKERS * 4, 1)
    n_chunks = min(n_chunks, 64, max(1, (len(files) + 499) // 500))
    chunk_sz = max(500, (len(files) + n_chunks - 1) // n_chunks)
    chunks = [files[i:i + chunk_sz] for i in range(0, len(files), chunk_sz)]

    def _clean_chunk(chunk):
        f = d = s = 0
        fails = []
        for fp, sz in chunk:
            if cancel_check and cancel_check():
                break
            try:
                if os.path.isfile(fp) or os.path.islink(fp):
                    os.remove(fp)
                    f += sz
                    d += 1
                else:
                    s += 1
            except (OSError, PermissionError) as e:
                s += 1
                fails.append((fp, str(e)))
        return f, d, s, fails

    with concurrent.futures.ThreadPoolExecutor(max_workers=CLEAN_WORKERS) as ex:
        futs = [ex.submit(_clean_chunk, c) for c in chunks]
        for fut in concurrent.futures.as_completed(futs):
            try:
                f, d, s, fails = fut.result()
            except Exception as e:
                _logger.warning("并行清理块异常: %s", e)
                continue
            freed += f
            deleted += d
            skipped += s
            for fp, msg in fails[:20]:  # 日志限流：每块最多记 20 条
                _logger.warning("删除失败: %s (%s)", fp, msg)
            if cancel_check and cancel_check():
                _logger.info("清理已取消（永久删除模式），已删除 %d 个", deleted)
                for ff in futs:
                    ff.cancel()
                break
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
