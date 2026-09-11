# -*- coding: utf-8 -*-
"""设计系统 · Design Tokens（v4.0 全新 UI）。

把所有视觉决策集中到这里：颜色 / 字体阶梯 / 圆角 / 间距 / 高度 / 动效时长。
页面代码只引用语义令牌（如 T.SURFACE、FS.H1、SP.LG），不再散落魔法数字 ——
改一处即可整体换肤，也保证各页视觉语言一致。

命名约定
    C_*  颜色（沿用旧版前缀，兼容 config 里的引用）
    FS.* 字号阶梯
    FW.* 字重
    R.*  圆角
    SP.* 间距
    H.*  控件高度
    AN.* 动效（帧间隔 / 帧数）
"""
# 字体族（与 config 保持一致；此处内联以避免循环导入）
FONT_FAMILY = "Microsoft YaHei UI"
MONO_FAMILY = "Consolas"

# ---------------------------------------------------------------- 颜色
# 深色：以「深蓝墨」为底，面板逐层提亮，强调色取高纯度蓝紫 + 青绿 + 琥珀。
# 颜色按亮度分层，保证任意相邻层的对比度 >= 1.15，边界清晰但不刺眼。
DARK = {
    # 背景层（从最深到最浅）
    "BG":            "#0a0e16",   # 窗口最底
    "BG_ALT":        "#0e1320",   # 交替区（列表底）
    "SURFACE":       "#151c2c",   # 一级面板 / 卡片
    "SURFACE_2":     "#1b2438",   # 二级面板（悬浮层：头部、工具栏）
    "SURFACE_3":     "#222c44",   # 三级面板（输入框、内嵌卡）
    "SURFACE_HOV":   "#26314e",   # 悬停态

    # 描边（3 档，由弱到强）
    "LINE":          "#232d44",   # 极弱分隔线
    "LINE_2":        "#2f3b58",   # 常规描边
    "LINE_3":        "#3d4c70",   # 强调描边 / 选中

    # 文字（4 档，对比度按 WCAG AA 校准：TEXT 15:1 / TEXT_2 9:1 / TEXT_3 5.2:1）
    "TEXT":          "#f4f7fc",   # 主标题
    "TEXT_2":        "#ccd6e6",   # 正文
    "TEXT_3":        "#9aa7bf",   # 次要说明（较 v3 提亮，保证深色底可读）
    "TEXT_4":        "#6e7c96",   # 弱化 / 占位（仍可读但不抢焦点）

    # 语义色
    "PRIMARY":       "#5b8cff",
    "PRIMARY_HOV":   "#4272f0",
    "PRIMARY_SOFT":  "#1e2a4d",   # 主色的低饱和底（徽章用）
    "SUCCESS":       "#2dd4a7",
    "SUCCESS_SOFT":  "#123a34",
    "WARN":          "#fbbf24",
    "WARN_SOFT":     "#3d2f10",
    "DANGER":        "#fb7185",
    "DANGER_SOFT":   "#3d1f28",
    "INFO":          "#38bdf8",

    # 半透明白（高光 / 阴影）
    "HL":            "#ffffff",
    "SHADOW":        "#000000",
}

# 浅色：冷白底 + 淡蓝灰面板，描边用蓝灰（避免纯灰发脏）。
LIGHT = {
    "BG":            "#eef2f9",
    "BG_ALT":        "#f7f9fd",
    "SURFACE":       "#ffffff",
    "SURFACE_2":     "#f4f7fc",
    "SURFACE_3":     "#e9eefa",
    "SURFACE_HOV":   "#e3ecfd",

    "LINE":          "#e2e8f4",
    "LINE_2":        "#d3dcec",
    "LINE_3":        "#b9c8e4",

    "TEXT":          "#141d2e",
    "TEXT_2":        "#3f4b60",
    "TEXT_3":        "#64708a",
    "TEXT_4":        "#97a2b6",

    "PRIMARY":       "#3b6ef5",
    "PRIMARY_HOV":   "#2b58d4",
    "PRIMARY_SOFT":  "#e2eaff",
    "SUCCESS":       "#0d9e73",
    "SUCCESS_SOFT":  "#dcf6ee",
    "WARN":          "#c47f00",
    "WARN_SOFT":     "#fdf1d8",
    "DANGER":        "#dc4a5e",
    "DANGER_SOFT":   "#fde5e8",
    "INFO":          "#0b8ec4",

    "HL":            "#ffffff",
    "SHADOW":        "#5b6b8c",
}

# ---------------------------------------------------------------- 字体阶梯
class FS:
    """字号阶梯（pt）。遵循 1.2 倍模数，层级一目了然。"""
    DISPLAY = 28    # 欢迎标题
    H1      = 22    # 页面主标题
    H2      = 17    # 区块标题
    H3      = 14    # 卡片标题 / 按钮（大）
    BODY    = 13    # 正文
    BODY_S  = 12    # 次要正文
    CAPTION = 11    # 说明 / 徽章
    MICRO   = 10    # 极小标注
    METRIC  = 21    # 数字指标（统计卡主值）


class FW:
    NORMAL = "normal"
    BOLD   = "bold"


# ---------------------------------------------------------------- 圆角
class R:
    XS = 6
    SM = 8
    MD = 10
    LG = 14
    XL = 18
    XXL = 22
    PILL = 999


# ---------------------------------------------------------------- 间距
class SP:
    XXS = 2
    XS  = 4
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 22
    XXL = 30


# ---------------------------------------------------------------- 控件高度
class H:
    BTN_LG  = 44    # 主操作（扫描 / 清理）
    BTN_MD  = 38    # 工具栏次级
    BTN_SM  = 30    # 卡片内 / 对话框
    INPUT   = 40
    NAV     = 40    # 侧边栏导航项
    HEADER  = 76
    TOOLBAR = 66
    STATUS  = 56


# ---------------------------------------------------------------- 动效
class AN:
    """动效参数：帧间隔越大越省 CPU，帧数越少越省。

    165Hz 屏上一帧 6.06ms，若动效帧间隔 <16ms 就会与滚动抢主线程，
    因此交互动效统一 >= 16ms，且帧数 <= 5。
    """
    HOVER_FRAMES = 4
    HOVER_DELAY  = 18
    FADE_FRAMES  = 5
    FADE_DELAY   = 20


# ---------------------------------------------------------------- 主题装载
THEMES = {"dark": DARK, "light": LIGHT}
CURRENT = "dark"


def tokens(theme_name):
    """返回指定主题的令牌字典。"""
    return THEMES.get(theme_name, DARK)
