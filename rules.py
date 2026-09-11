# -*- coding: utf-8 -*-
"""C盘垃圾清理工具 · 清理规则模块（垃圾类型分类 / 规则构建）。"""
import os
import glob

from config import LOCAL, APP, PF, PFX, PD, HOME

FOLDER_NAME_TO_TYPE = {
    "cache": "缓存", "caches": "缓存", "cached": "缓存",
    "gpucache": "GPU缓存",
    "code cache": "代码缓存",
    "shadercache": "着色器缓存", "dxcache": "DX缓存", "glcache": "GL缓存",
    "mediacache": "媒体缓存", "mediacachefiles": "媒体缓存",
    "webcache": "网页缓存", "web-cache": "网页缓存", "http cache": "HTTP缓存",
    "appcache": "应用缓存", "depotcache": "Depot缓存",
    "temp": "临时文件", "tmp": "临时文件", "temporary": "临时文件", "temps": "临时文件",
    "logs": "日志", "log": "日志",
    "crashpad": "崩溃数据", "crashreports": "崩溃报告",
    "crashes": "崩溃数据", "crashdumps": "崩溃转储",
    "thumbnails": "缩略图",
    "service worker": "Service Worker",
    "blobstorage": "Blob存储", "blob_storage": "Blob存储",
    "session storage": "会话存储",
    "databases": "数据库",
    "dvdcss": "DVD解密缓存",
    ".dropbox.cache": "云盘缓存",
    "browser-profile": "浏览器配置", "browserprofile": "浏览器配置",
}

# 扩展名 -> 垃圾类型（文件级匹配的归类）
EXT_TO_TYPE = {
    ".log": "日志文件",
    ".tmp": "临时文件", ".temp": "临时文件",
    ".bak": "备份文件", ".old": "备份文件",
    ".cache": "缓存文件",
    ".crdownload": "下载残留", ".part": "下载残留", ".download": "下载残留",
    ".dmp": "崩溃转储", ".etl": "事件追踪日志",
    ".swp": "交换文件", ".swo": "交换文件",
    ".~": "临时文件",
}

# 垃圾类型 -> 徽章颜色
TYPE_COLORS = {
    "缓存": "#5b8cff", "缓存文件": "#5b8cff", "应用缓存": "#5b8cff", "Depot缓存": "#5b8cff",
    "GPU缓存": "#8b5cf6", "代码缓存": "#6366f1",
    "着色器缓存": "#a855f7", "DX缓存": "#9333ea", "GL缓存": "#9333ea",
    "媒体缓存": "#06b6d4", "网页缓存": "#0ea5e9", "HTTP缓存": "#0ea5e9",
    "云盘缓存": "#06b6d4", "DVD解密缓存": "#5b8cff", "浏览器配置": "#0ea5e9",
    "临时文件": "#fbbf24", "下载残留": "#fbbf24", "交换文件": "#fbbf24", "备份文件": "#fbbf24",
    "日志": "#22d3a0", "日志文件": "#22d3a0", "事件追踪日志": "#22d3a0",
    "崩溃数据": "#f87171", "崩溃报告": "#f87171", "崩溃转储": "#f87171",
    "缩略图": "#14b8a6",
    "Service Worker": "#ec4899",
    "Blob存储": "#f97316",
    "会话存储": "#84cc16",
    "数据库": "#eab308",
    "其他": "#64748b",
}


def classify_junk_type(dirpath_segs, ext):
    """根据文件夹路径段（小写列表）与文件扩展名判断垃圾类型。"""
    for seg in dirpath_segs:
        if seg in FOLDER_NAME_TO_TYPE:
            return FOLDER_NAME_TO_TYPE[seg]
    if ext and ext in EXT_TO_TYPE:
        return EXT_TO_TYPE[ext]
    return "其他"


# ---------- 工具函数 ----------

JUNK_FOLDER_NAMES = {
    "cache", "caches", "cached", "temp", "tmp", "temporary", "temps",
    "logs", "log", "crashpad", "crashreports", "crashes", "crashdumps",
    "gpucache", "code cache", "service worker", "shadercache", "dxcache",
    "glcache", "mediacache", "mediacachefiles", "thumbnails", "webcache",
    "web-cache", "http cache", "blobstorage", "blob_storage",
    "session storage", "databases", "depotcache", "appcache",
    "dvdcss", ".dropbox.cache", "browser-profile", "browserprofile",
}
JUNK_EXTENSIONS = {
    ".log", ".tmp", ".temp", ".bak", ".old", ".cache", ".crdownload",
    ".part", ".download", ".dmp", ".etl", ".swp", ".swo", ".~",
}
SKIP_SEGMENTS = {
    "node_modules", ".git", "obj", "bin", "packages", "site-packages",
    "vendor", ".venv", "venv", "user data", "users", "profiles", "profile",
    "documents", "desktop", "downloads", "pictures", "music", "videos",
    "mail", "contacts", "onedrive", "filestorage", "config", "preferences",
    "resources", "assets", "data", "wwwroot", "public", "src", "lib",
}
DEEP_CAP = 400000
APP_FOLDER_NAME_MAP = {
    "discord": "Discord", "slack": "Slack", "code": "Visual Studio Code",
    "jetbrains": "JetBrains IDE", "spotify": "Spotify", "obs-studio": "OBS Studio",
    "epicgameslauncher": "Epic Games Launcher", "origin": "EA / Origin",
    "battle.net": "Battle.net", "ubisoft game launcher": "Ubisoft Connect",
    "gog.com": "GOG Galaxy", "bravesoftware": "Brave Browser",
    "google": "Google Chrome / Google 应用", "mozilla": "Mozilla Firefox",
    "opera software": "Opera", "adobe": "Adobe", "baidu": "百度网盘",
    "dropbox": "Dropbox", "nvidia": "NVIDIA", "amd": "AMD Software", "intel": "Intel",
}

# ---------- 软件更新安装包识别配置 ----------
# 安装包扩展名

INSTALLER_EXTENSIONS = {".exe", ".msi", ".msu", ".cab", ".msp"}
# 更新/安装包类目录名（命中后其中的安装包文件纳入扫描）
UPDATE_FOLDER_NAMES = {
    "update", "updates", "updater", "download", "downloads",
    "installer", "installers", "setup", "setupfiles",
    "packages", "distribution", "redist", "redistributable",
    "webinstall", "websetup", "bootstrapper",
}
# 文件名关键词：命中后即使不在 update 目录也视为安装包（提升召回）
INSTALLER_NAME_KEYWORDS = (
    "setup", "install", "update", "upgrade", "patch",
    "redist", "bootstrapper", "webinstall", "client",
)
# 更新安装包扫描的剪枝段（比 deep 宽松：允许 download/downloads/installer 等，因为
# 扫描根目录仅限 AppData/ProgramData，不会触及个人 Downloads/Desktop）
UPDATE_SKIP_SEGMENTS = {
    "node_modules", ".git", "obj", "bin", "packages", "site-packages",
    "vendor", ".venv", "venv", "src", "lib", "resources", "assets",
    "wwwroot", "public", "cache", "caches", "temp", "tmp", "logs",
    "service worker", "gpucache", "shadercache",
}
# 安装包最小体积阈值：<1MB 的不纳入（避免把小工具/配置当安装包）
INSTALLER_MIN_SIZE = 1024 * 1024

# ---------- 规则构建 ----------

# 清理项分类（v3.0：侧边栏导航分组依据；key -> 分类）
RULE_CAT = {}
RULE_CAT.update({k: "system" for k in (
    "win_temp", "user_temp", "recycle", "prefetch", "wsus", "delivery",
    "thumb", "wer", "winlogs", "crashdumps")})
RULE_CAT.update({k: "browser" for k in (
    "chrome_cache", "edge_cache", "firefox_cache", "opera_cache", "brave_cache")})
RULE_CAT.update({k: "app" for k in ("discord", "slack", "teams", "wechat")})
RULE_CAT.update({k: "dev" for k in (
    "vscode", "jetbrains", "npm_cache", "pip_cache", "android_studio")})
RULE_CAT.update({k: "game" for k in (
    "steam", "epic", "ea_origin", "ubisoft", "gog", "battlenet")})
RULE_CAT.update({k: "media" for k in (
    "adobe_mediacache", "adobe_logs", "spotify", "obs")})
RULE_CAT.update({k: "cloud" for k in ("dropbox", "baidu", "onedrive_logs")})
RULE_CAT.update({k: "driver" for k in ("nvidia", "amd", "intel")})
RULE_CAT["deep_apps"] = "deep"
RULE_CAT["update_packages"] = "update"

def _glob(patterns):
    out = []
    for p in patterns:
        if "*" in p or "?" in p:
            out.extend(glob.glob(p))
        else:
            out.append(p)
    seen = set()
    res = []
    for p in out:
        if p and p not in seen and os.path.exists(p):
            seen.add(p)
            res.append(p)
    return res


# ---------- 默认选中与风险提示 ----------
# default_on=False 的项默认不勾选；warn 会在卡片上以 ⚠ 标识，
# 并在清理确认框中列出后果（用户勾选后再告知，而不是默默全选）。
CAREFUL_WARN = {
    "recycle": "会清空回收站且不可恢复，清理前请确认没有放错的文件。",
    "prefetch": "删除后开机与软件首次启动会稍慢，系统会自动重建。",
    "thumb": "删除后图片/视频文件夹缩略图需重新生成，首次打开会变慢。",
    "nvidia": "删除后游戏首次运行需重新编译着色器，会卡顿、加载变慢，玩一会儿自动恢复。",
    "amd": "删除后游戏首次运行需重新编译着色器，会卡顿、加载变慢，玩一会儿自动恢复。",
    "intel": "删除后部分软件/游戏首次运行需重新编译着色器，短暂变慢后恢复。",
    "steam": "包含 Steam 下载目录，删除后游戏内容需重新下载，请确认没有未备份的游戏。",
    "adobe_mediacache": "删除后 PR/AE 打开旧工程需重新生成预览渲染，耗时较长。",
    "deep_apps": "激进模式：覆盖所有第三方应用，建议点「查看归属」逐项确认后再清理。",
    "update_packages": "删除后软件无法本地重装/回滚，出问题只能重新下载安装包。",
}


def build_rules():
    R = []

    # ===== 系统垃圾 =====
    R.append(dict(key="win_temp", name="Windows 临时文件", desc="C:\\Windows\\Temp 系统临时文件",
                  type="path", paths=[r"C:\Windows\Temp"], recursive=True, pattern="*"))
    R.append(dict(key="user_temp", name="用户临时文件", desc="当前用户 Temp 目录临时文件",
                  type="path", paths=[os.path.join(LOCAL, "Temp")], recursive=True, pattern="*"))
    R.append(dict(key="recycle", name="回收站", desc="C 盘回收站中已删除的文件",
                  type="path", paths=[r"C:\$Recycle.Bin"], recursive=True, pattern="*"))
    R.append(dict(key="prefetch", name="预读取文件", desc="C:\\Windows\\Prefetch 加速缓存",
                  type="path", paths=[r"C:\Windows\Prefetch"], recursive=False, pattern="*"))
    R.append(dict(key="wsus", name="Windows 更新缓存", desc="SoftwareDistribution\\Download 更新备份",
                  type="path", paths=[r"C:\Windows\SoftwareDistribution\Download"], recursive=True, pattern="*"))
    R.append(dict(key="delivery", name="传递优化缓存", desc="DeliveryOptimization 分发缓存",
                  type="path", paths=[r"C:\Windows\SoftwareDistribution\DeliveryOptimization\Cache"], recursive=True, pattern="*"))
    R.append(dict(key="thumb", name="缩略图缓存", desc="资源管理器缩略图数据库 thumbcache_*.db",
                  type="path", paths=[os.path.join(LOCAL, "Microsoft", "Windows", "Explorer")], recursive=False, pattern="thumbcache_*.db"))
    R.append(dict(key="wer", name="系统错误报告", desc="Windows Error Reporting 错误转储",
                  type="path", paths=[os.path.join(LOCAL, "Microsoft", "Windows", "WER")], recursive=True, pattern="*"))
    R.append(dict(key="winlogs", name="Windows 系统日志缓存", desc="C:\\Windows\\Logs 下的 CBS/DISM/更新日志",
                  type="path", paths=[r"C:\Windows\Logs"], recursive=True, pattern="*"))
    R.append(dict(key="crashdumps", name="系统崩溃转储", desc="AppData 下的用户态崩溃转储 .dmp",
                  type="path", paths=[os.path.join(LOCAL, "CrashDumps")], recursive=True, pattern="*"))

    # ===== 浏览器 =====
    chrome_base = os.path.join(LOCAL, "Google", "Chrome", "User Data", "Default")
    edge_base = os.path.join(LOCAL, "Microsoft", "Edge", "User Data", "Default")
    R.append(dict(key="chrome_cache", name="Chrome 浏览器缓存", desc="Google Chrome 各类缓存与 Service Worker",
                  type="path", paths=_glob([os.path.join(chrome_base, x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Media Cache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="edge_cache", name="Edge 浏览器缓存", desc="Microsoft Edge 各类缓存与 Service Worker",
                  type="path", paths=_glob([os.path.join(edge_base, x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Media Cache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="firefox_cache", name="Firefox 浏览器缓存", desc="Mozilla Firefox 缓存与缩略图",
                  type="path", paths=_glob([
                      os.path.join(APP, "Mozilla", "Firefox", "Profiles", "*", "cache2"),
                      os.path.join(APP, "Mozilla", "Firefox", "Profiles", "*", "startupCache"),
                      os.path.join(APP, "Mozilla", "Firefox", "Profiles", "*", "thumbnails")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="opera_cache", name="Opera 浏览器缓存", desc="Opera Stable 缓存",
                  type="path", paths=_glob([os.path.join(APP, "Opera Software", "Opera Stable", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "Media Cache"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="brave_cache", name="Brave 浏览器缓存", desc="Brave Browser 各类缓存",
                  type="path", paths=_glob([os.path.join(LOCAL, "BraveSoftware", "Brave-Browser", "User Data", "Default", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "Media Cache"]]),
                  recursive=True, pattern="*"))

    # ===== 通讯 / 协作 =====
    R.append(dict(key="discord", name="Discord 缓存", desc="Discord 缓存 / GPUCache / Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "discord", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="slack", name="Slack 缓存", desc="Slack 缓存与 Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "Slack", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="teams", name="Microsoft Teams 缓存", desc="Teams 缓存 / 临时 / Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "Microsoft", "Teams", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "tmp"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="wechat", name="微信缓存/临时", desc="WeChat Files 下的 Cache/Temp/Thumb（不含聊天文件）",
                  type="path", paths=_glob([
                      os.path.join(HOME, "Documents", "WeChat Files", "*", "FileStorage", "Cache"),
                      os.path.join(HOME, "Documents", "WeChat Files", "*", "FileStorage", "Temp"),
                      os.path.join(HOME, "Documents", "WeChat Files", "*", "FileStorage", "Thumb")]),
                  recursive=True, pattern="*"))

    # ===== 开发工具 =====
    R.append(dict(key="vscode", name="VS Code 缓存/日志", desc="Visual Studio Code 缓存、日志与 Service Worker",
                  type="path", paths=_glob([os.path.join(APP, "Code", x) for x in
                      ["Cache", "Code Cache", "GPUCache", "Service Worker", "CachedData", "logs", "blob_storage"]]),
                  recursive=True, pattern="*"))
    R.append(dict(key="jetbrains", name="JetBrains IDE 缓存", desc="IDEA/PyCharm/WebStorm 等缓存、日志、临时",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "JetBrains", "*", "caches"),
                      os.path.join(LOCAL, "JetBrains", "*", "log"),
                      os.path.join(LOCAL, "JetBrains", "*", "tmp")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="npm_cache", name="npm 缓存", desc="Node.js npm 全局缓存",
                  type="path", paths=[os.path.join(APP, "npm-cache")], recursive=True, pattern="*"))
    R.append(dict(key="pip_cache", name="pip 缓存", desc="Python pip 下载缓存",
                  type="path", paths=[os.path.join(LOCAL, "pip", "Cache")], recursive=True, pattern="*"))
    R.append(dict(key="android_studio", name="Android Studio 缓存", desc="Android Studio 系统缓存与日志",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "Google", "AndroidStudio*", "system", "caches"),
                      os.path.join(LOCAL, "Google", "AndroidStudio*", "system", "log"),
                      os.path.join(LOCAL, "Google", "AndroidStudio*", "system", "tmp")]),
                  recursive=True, pattern="*"))

    # ===== 游戏平台 =====
    steam_paths = []
    for base in (PF, PFX, LOCAL):
        sp = os.path.join(base, "Steam")
        if os.path.isdir(sp):
            steam_paths += [os.path.join(sp, x) for x in ("downloads", "appcache", "logs", "tmp")]
    R.append(dict(key="steam", name="Steam 下载/更新缓存", desc="Steam 下载缓存、appcache、日志、临时",
                  type="path", paths=_glob(steam_paths), recursive=True, pattern="*"))
    R.append(dict(key="epic", name="Epic 游戏平台缓存", desc="EpicGamesLauncher 日志/崩溃/webcache",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "EpicGamesLauncher", "Saved", "Logs"),
                      os.path.join(LOCAL, "EpicGamesLauncher", "Saved", "Crashes"),
                      os.path.join(LOCAL, "EpicGamesLauncher", "Saved", "webcache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="ea_origin", name="EA / Origin 缓存", desc="Origin 头像/网页缓存与日志（不含云存档）",
                  type="path", paths=_glob([
                      os.path.join(APP, "Origin", "Logs"),
                      os.path.join(LOCAL, "Origin", "AvatarsCache"),
                      os.path.join(LOCAL, "Origin", "Web Cache"),
                      os.path.join(LOCAL, "Origin", "Logs")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="ubisoft", name="Ubisoft Connect 缓存", desc="Ubisoft Game Launcher 缓存/日志/临时",
                  type="path", paths=_glob([os.path.join(LOCAL, "Ubisoft Game Launcher", x) for x in
                      ("cache", "logs", "temp")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="gog", name="GOG Galaxy 缓存", desc="GOG.com Galaxy 缓存与日志",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "GOG.com", "Galaxy", "Cache"),
                      os.path.join(PD, "GOG.com", "Galaxy", "Logs")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="battlenet", name="战网 Battle.net 缓存", desc="Battle.net 缓存与日志",
                  type="path", paths=_glob([
                      os.path.join(APP, "Battle.net", "Cache"),
                      os.path.join(PD, "Battle.net", "Cache"),
                      os.path.join(PD, "Battle.net", "Logs")]),
                  recursive=True, pattern="*"))

    # ===== 媒体 / 设计 =====
    R.append(dict(key="adobe_mediacache", name="Adobe 媒体缓存", desc="Adobe Common 媒体缓存/峰值文件（常达数 GB）",
                  type="path", paths=_glob([
                      os.path.join(APP, "Adobe", "Common", "Media Cache*"),
                      os.path.join(LOCAL, "Adobe", "Common", "Media Cache*")]),
                  recursive=True, pattern="*"))
    # 注意：只扫各软件的日志/缓存/临时子目录 —— 整目录扫描会误删
    # 色彩配置文件(Color/Profiles)、Acrobat 偏好、授权标记(licflags)等用户数据。
    R.append(dict(key="adobe_logs", name="Adobe 日志缓存", desc="Adobe 各软件日志/缓存/临时（不含配置与预设）",
                  type="path", paths=_glob([
                      os.path.join(LOCAL, "Adobe", "*", "Logs"),
                      os.path.join(LOCAL, "Adobe", "*", "logs"),
                      os.path.join(LOCAL, "Adobe", "*", "log"),
                      os.path.join(LOCAL, "Adobe", "*", "Cache"),
                      os.path.join(LOCAL, "Adobe", "*", "Temp"),
                      os.path.join(LOCAL, "Adobe", "Acrobat", "*", "Cache"),
                      os.path.join(LOCAL, "Adobe", "Acrobat", "*", "Logs")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="spotify", name="Spotify 日志", desc="Spotify 日志与浏览器缓存",
                  type="path", paths=_glob([os.path.join(LOCAL, "Spotify", "Logs"),
                                            os.path.join(LOCAL, "Spotify", "Browser-profile", "Cache")]),
                  recursive=True, pattern="*"))
    # 注意：只扫日志/崩溃/更新子目录 —— 整目录扫描会删掉 basic/ 下的
    # 场景与配置文件以及插件配置，导致直播/录制设置丢失。
    R.append(dict(key="obs", name="OBS Studio 缓存", desc="OBS 日志/崩溃报告/更新包（不含场景与配置）",
                  type="path", paths=_glob([os.path.join(APP, "obs-studio", x) for x in
                      ("logs", "crashes", "updates")]),
                  recursive=True, pattern="*"))

    # ===== 云盘 =====
    R.append(dict(key="dropbox", name="Dropbox 缓存", desc=".dropbox.cache 与日志",
                  type="path", paths=_glob([os.path.join(LOCAL, ".dropbox.cache"), os.path.join(LOCAL, "Dropbox", "logs")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="baidu", name="百度网盘缓存", desc="BaiduNetdisk 缓存/日志/webcache",
                  type="path", paths=_glob([os.path.join(LOCAL, "baidu", "BaiduNetdisk", x) for x in
                      ("cache", "logs", "webcache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="onedrive_logs", name="OneDrive 日志", desc="Microsoft OneDrive 日志",
                  type="path", paths=_glob([os.path.join(LOCAL, "Microsoft", "OneDrive", "logs")]),
                  recursive=True, pattern="*"))

    # ===== 驱动 / 显卡 =====
    R.append(dict(key="nvidia", name="NVIDIA 着色器缓存", desc="NVIDIA DXCache / GLCache 着色器缓存",
                  type="path", paths=_glob([os.path.join(LOCAL, "NVIDIA", x) for x in ("DXCache", "GLCache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="amd", name="AMD 着色器缓存", desc="AMD GLCache / DXCache",
                  type="path", paths=_glob([os.path.join(LOCAL, "AMD", "GLCache"), os.path.join(LOCAL, "AMD", "DXCache")]),
                  recursive=True, pattern="*"))
    R.append(dict(key="intel", name="Intel 着色器缓存", desc="Intel ShaderCache",
                  type="path", paths=_glob([os.path.join(LOCAL, "Intel", "ShaderCache")]),
                  recursive=True, pattern="*"))

    # ===== 深度扫描：第三方应用残留 =====
    R.append(dict(key="deep_apps", name="第三方深度清理",
                  desc="遍历 AppData/ProgramData 中的 cache/temp/logs 目录与 .log/.tmp/.bak/.dmp 等垃圾文件",
                  type="deep", roots=[p for p in (LOCAL, APP, PD) if p and os.path.isdir(p)],
                  recursive=True, pattern="*"))

    # ===== 软件更新安装包 =====
    R.append(dict(key="update_packages", name="软件更新安装包",
                  desc="扫描各软件下载的更新安装包（.exe/.msi/.cab 等），可按软件来源展开查看文件名/版本/大小",
                  type="update", roots=[p for p in (LOCAL, APP, PD) if p and os.path.isdir(p)],
                  recursive=True, pattern="*"))

    R = [r for r in R if (r.get("paths") or r.get("roots"))]
    for r in R:
        r["cat"] = RULE_CAT.get(r.get("key"), "system")
        # 默认选中分级：需用户确认的项默认不勾选，并附风险说明
        w = CAREFUL_WARN.get(r.get("key"))
        if w:
            r["default_on"] = False
            r["warn"] = w
        else:
            r["default_on"] = True
    # 深度扫描去重：排除已被专项规则覆盖的目录，
    # 避免同一文件在 nvidia/amd 等专项与 deep_apps 中被计算两次
    # （总量虚高、清理时还会重复删除同一文件）。
    _prefixes = []
    for r in R:
        if r.get("type") == "path":
            for p in r.get("paths", []):
                try:
                    _prefixes.append(os.path.normcase(os.path.normpath(p)))
                except Exception:
                    pass
    for r in R:
        if r.get("type") == "deep":
            r["exclude_prefixes"] = _prefixes
    return R

# ---------- 扫描 / 清理核心 ----------
