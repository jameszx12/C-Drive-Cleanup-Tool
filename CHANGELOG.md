# 更新历史

## v4.1.0（2026-09-11）去重 + 默认选中分级 + 风险提示

### 用户反馈
"英伟达着色器缓存计算了两次，在第三方深度清理里还计算了一次。默认不要全选，默认选上不重要的选项。如果用户要选上重要的选项告诉他会发生什么事情"

### 根因
- `deep_apps` 全量遍历 AppData/ProgramData 下的 cache/temp/logs，而 nvidia/amd 等专项规则的目录正好落在该范围内 → 同一文件被两个规则各计一次，总量虚高
- `_add_row(rule, selected=True)` 默认全选，回收站/着色器缓存等需确认项也被默默勾选

### 修复
- **去重**：`build_rules()` 收集全部专项 path 规则目录存入 deep 规则的 `exclude_prefixes`；`scan_deep_rule()` 整棵子树跳过已覆盖目录（专项与 deep 零重叠已验证）
- **默认选中分级**：`rules.CAREFUL_WARN` 定义 13 项需确认项（回收站/预读取/缩略图/三家着色器缓存/Steam 下载/EA 登录态/OBS 配置/Adobe 日志与媒体缓存/深度清理/更新安装包），`default_on=False`；其余安全项默认勾选
- **风险告知**：风险卡片底行显示 `⚠ 需确认`（悬停 Tooltip 看后果）；清理确认框逐条列出已勾选风险项的后果（如"着色器缓存删除后游戏首次运行需重新编译，会卡顿、加载变慢"）

### 验证
- 合成目录验证：无排除时 2 文件 → 有排除后仅未知应用文件被计入；真实规则 deep 自带 32 条排除前缀
- GUI 验证：安全卡默认 on、风险卡默认 off、`⚠ 需确认`标识存在、显式 selected 参数仍优先
- `smoke_gui_test` / `test_regress` / `selftest` 全部通过

## v3.0.4（2026-08-05）毛玻璃四周透出恢复

### 用户反馈
"毛玻璃半透明效果只有最上面还有，其他地方的毛玻璃半透明效果消失了"

### 根因（v3.0.2 改坏的）
- v3.0.2 把 `_build_shell` 的 `self.content` 从 transparent 改成 `fg_color=C_BG`
- content 用 `pack(fill="both", expand=True)` **铺满整个窗口客户区**
- 结果：毛玻璃仅在窗口外框 0px（被 content 完全覆盖）+ 系统标题栏（DWM 自己的 acrylic）
  → 用户看到"只有最上面还有效果，其他地方都消失了"
- v3.0.2 的错误推理：「content 不透明后毛玻璃仅在最外层边距（padx=16）透出」
  ——但 content fill=both expand 已经占满整个窗口，没有"最外层边距"裸露

### 正确修复
- **content 恢复 transparent**（v3.0.0 原状）
- 防伪影依靠 `_build_list_area` 的 scroll `fg_color=C_BG`（v3.0.2 已正确实施）：
  卡片圆角外区域 = list_container (transparent) → scroll (C_BG) → 不透明，零伪影
- 边距毛玻璃区域：header 上 16px / body 左右 16px / status 下 16px / main 与 sidebar 之间 12px
  全部由 content (transparent) → 窗口键色 → DWM acrylic 透出
- 对话框 content 本来就是 transparent（v3.0.1 起），list_frame 也已 C_BG（v3.0.2），无需改动

### 验证
- PIL ImageGrab 截图：开启毛玻璃时窗口四周（上下左右）全部透出桌面背景+任务栏；
  卡片/面板边缘干净无紫边；统计卡小字完整显示；关闭时纯色外观不变

## v3.0.3（2026-08-05）统计卡副标题完整显示

### 用户反馈
"统计卡副标题清晰可读下面的小字还是看不见，因为这个表头太矮了，没显示完全"

### 根因
- 工具栏固定 height=72，inner pady=12 → 内容区仅 48px
- 统计卡原始布局：icon width=22 pady=10（≈42px）+ col_c pady=8 + 14pt bold（≈19px）+ 10pt（≈14px）= ≈49px
- 49px > 48px → 副标题（第二行）被工具栏底部裁剪；DPI 缩放 125%/150% 时溢出更严重

### 修复
- icon：width 22→18，pady 10→8，image 20px→18px（≈34px）
- col_c：pady 8→3，padx 14→12（≈39px）
- 统计卡总高 39px，比 inner 内容区 48px 留 9px 余量；DPI 缩放下仍完整可见
- 主值保持 14pt 粗体（醒目），副标题保持 10pt + C_TEXT_DIM（对比度足够）

### 验证
- 编译通过
- PIL ImageGrab 放大截图统计卡区域：两行「10,747 / 已发现文件」「9.14 GB / 预计可释放」均完整可见

## v3.0.2（2026-08-05）修复毛玻璃紫边/设置滚动/统计卡小字

### 用户反馈后修的
- **「卡片边缘有紫色，不好看」**：v3.0.1 开启毛玻璃时 CTk 圆角控件（卡片/行）在
  透明窗口上有边缘伪影（圆角外透出背景色 → 紫边），与「平滑过渡、正常边缘」
  相悖。v3.0.2 修复：
  - 毛玻璃**默认关闭**（DEFAULT glass_mode False）
  - 即使开启毛玻璃，列表/对话框的滚动区固定 `C_BG` 不透明 → 圆角控件
    圆角外区域显示 C_BG（不透明），毛玻璃仅在最外层窗口边距（padx=16）
    透出 DWM 模糊背景；既保留「缝隙毛玻璃」效果又无任何圆角伪影
  - 关闭毛玻璃时正确清除 `-transparentcolor` 残留
- **「设置没有滑动按键，看不到下面的内容」**：v3.0.1 设置窗口 520x540
  内容（主题+回收站+毛玻璃+日志+按钮）总高 ≈ 600+ 超出窗口高度，固定
  resizable=False 且无滚动 → 日志卡片和保存/取消按钮被裁剪看不到。
  v3.0.2 重构：选项卡片放入 `CTkScrollableFrame`，窗口改为 520x560，
  滚动条右侧可见，无论内容多少都能查看全部。
- **「最上面清理多少项目、多少内存下面的小字看不见」**：v3.0.0/v3.0.1
  统计卡副标题「已发现文件」「预计可释放」用 `C_TEXT_FAINT` (#64748b)
  在 `C_PANEL` (#111827) 上对比度太低，几乎不可见。v3.0.2 提升为
  `C_TEXT_DIM` (#94a3b8)，字号 9→10，清晰可读。

### 涉及文件
- config.py（VERSION v3.0.2，glass_mode 默认 False）
- app.py（_build_list_area 滚动区 fg→C_BG；统计卡副标题 C_TEXT_DIM + 字号 10）
- dialogs.py（SettingsDialog 重构为「固定 header + scroll + 固定 footer」三段式；
  _BaseDetailDialog._build_list 滚动区 fg→C_BG；毛玻璃开关提示文字更新）

### 验证
- py_compile + selftest / test_regress / smoke_gui_test 全绿
- PIL ImageGrab 截图：默认毛玻璃关闭时所有面板边缘干净无紫边；毛玻璃开启时
  桌面背景透过但卡片边缘依然干净；设置对话框可滚动看到所有卡片与底部按钮；
  统计卡小字清晰可见

### 核心改动
- **窗口缝隙毛玻璃**（用户要求「缝隙处增加半透明毛玻璃」）：
  - `glass.py` 的 `apply_acrylic`（DWM DWMWA_SYSTEMBACKDROP_TYPE / Win10 acrylic blur）应用到主窗口与所有对话框
  - 窗口背景真半透明 + 内容面板（头部/侧边栏/工具栏/状态栏/卡片）保持不透明 → **边距与卡片间隙透出系统级 Acrylic 模糊背景**，内容区域清晰可读
  - 设置项「窗口毛玻璃（缝隙半透明效果）」可开关，默认开；旧系统/不支持自动回退纯色
  - 关闭时正确清除 `-transparentcolor` 残留（避免颜色诡异）
- **卡片选中强调条**：选中卡片左侧 3px 圆角 accent 竖条，比仅边框变化更直观
- **进度条流动动画**：扫描/清理时 `CTkProgressBar.mode="indeterminate"`，条纹流动；结束自动回 determinate 显示百分比
- **清理残留 emoji**：卡片文件数前的 📄 替换为 file 线性图标
- **设置对话框主题分段选中态实时刷新**：v3.0.0 实现时 `_select_theme` 只设 StringVar 视觉不变；v3.0.1 给 GlassButton 加 `set_accent()` 重算配色，点击「浅色/跟随系统/深色」即时切换高亮
- **GlassButton 配色逻辑抽出 `_compute_fg(accent)` + `set_accent(accent)`**：便于运行时切换主题色（不影响现有 init 行为）

### 验证
- py_compile + selftest / test_regress / smoke_gui_test 全绿
- PIL ImageGrab 截图（沙箱桌面背景透出紫红色发光边，证明 DWM 真毛玻璃生效）：
  - 主窗口边距、卡片间隙透出模糊背景
  - 选中卡片左侧强调条（vs 未选中无）
  - 文件数图标：file 线性图标替代 📄
  - 设置对话框：主题分段选中态（深色高亮）+ 新增毛玻璃开关 + 每卡片边缘的紫色发光边

### 涉及文件
- config.py（VERSION v3.0.1 / glass_mode 默认 True）
- widgets.py（GlassButton._compute_fg + set_accent）
- app.py（_apply_backdrop 毛玻璃版 / 卡片选中强调条 / 文件数图标 / _start_progress_flow / 扫描清理 worker 去掉 per-rule set_progress）
- dialogs.py（_BaseDetailDialog / SettingsDialog 毛玻璃版 / 新增 _build_glass_card / _select_theme 刷新分段按钮）

### 核心改动
- **统一线性图标系统**：用 `@tabler/icons` 矢量源 + sharp 栅格化生成 PNG，替换全程序 emoji（🧹📄💾🔍🗑☐☑⚙⏻）与字符符号（▣◎◇）。明暗双变体（#a5b3cb 暗主题 / #53617a 亮主题）+ 多尺寸（18/20/22/24px），全程序视觉一致
  - 工具：tools/make_ui_icons.js（148 个 UI 图标）、tools/make_svg_icons.js（42 个规则图标，按分类着色：system #60a5fa / browser #22d3a0 / dev #38bdf8 / game #a855f7 / media #f472b6 / cloud #06b6d4 / driver #94a3b8 / deep #a78bfa）
  - 品牌图标：Chrome / Edge / Firefox / Opera / Discord / Slack / VS Code / npm / Python / Steam / Spotify / Adobe / AMD / Dropbox / 百度网盘 / 微信等均用 tabler 品牌线框图
  - widgets.py 新增 `ui_icon(name, size)` / `rule_icon_photo(key, size)`（PhotoImage 缓存 + 智能回退最近源尺寸）+ `Tooltip`（玻璃气泡悬浮提示）

### 布局重构
- **紧凑头部**（84px）：应用图标 + 标题 + 版本徽章 + 副标题；右上角三个 44×44 图标按钮（主题/设置/退出）+ Tooltip 提示
- **左侧分类导航侧边栏**（216px）：搜索框 + 全部项目 + 系统垃圾/浏览器/应用缓存/开发工具/游戏平台/媒体工具/云盘/驱动显卡/深度扫描/更新安装包；每项实时显示文件数 / 体积；点击过滤卡片列表
- **搜索**：侧边栏搜索框按名称/描述实时过滤卡片（与分类过滤组合）
- **工具栏**：核心（扫描/清理/取消）| 编辑（全选/全不选）+ 统计卡（已发现文件数 / 预计释放空间），设置/退出已上移头部，工具栏更聚焦主操作
- **卡片**：slim 150px 高；checkbox + 线性图标 + 名称 + 体积 + 描述 + 分类徽章 + 文件数 + 📂 打开按钮（带 Tooltip）；深/更新类型额外显示「查看归属/查看安装包」按钮

### 交互优化
- **键盘快捷**：Enter / F5 启动扫描；Ctrl+A / Ctrl+Shift+A 全选 / 全不选
- **焦点环**：GlassButton 按 Tab 导航时显示 2px 圆角描边（C_PRIMARY_GLOW 暗主题 / C_PRIMARY 亮主题）
- **Toast 轻量通知**：扫描完成 / 清理完成 / 未发现垃圾 / 取消等非阻塞反馈替换原 mb.showinfo；右上角玻璃气泡 + alpha 渐变动画；安全确认（清理）仍用原生对话框
- **主题三态**：浅色 / 深色 / 跟随系统（darkdetect），点击主题图标循环切换；设置对话框新增主题分段控件
- **勾选状态跨过滤/主题保留**：新增 `self._sel_state` 字典；切换分类或主题后卡片复选框状态保持

### 代码质量
- **dialogs.py 提取 `_BaseDetailDialog`**：消除 FolderDetail 与 PackageDetail 两对话框 ~400 行布局代码重复
- **SettingsDialog 重做**：玻璃分组卡片 + 主题分段控件（浅色/跟随系统/深色）+ 回收站模式 + 日志路径
- **widgets.py**：`make_badge` 统一徽章工厂；GlassButton 支持键盘焦点环
- **icons.py**：暴露 `resource_dir()` 公共函数（之前内部别名）
- **rules.py**：每条规则新增 `cat` 字段（10 个分类）供侧边栏导航
- **config.py**：VERSION v3.0.0；`CURRENT_THEME` 全局；`detect_system_theme()` 函数（darkdetect）

### 验证
- py_compile + selftest / test_regress / smoke_gui_test 全绿
- PIL ImageGrab 截图确认：暗色/亮色主题均渲染完美（侧边栏分类+卡片+统计卡+工具栏图标全部正常）

- **拉大卡片与背景色差**：dark 主题 C_GLASS #161b2b→#1d2438、C_GLASS_2 #1a2033→#232b42、C_GLASS_BORDER #2f3a55→#3d4d75（卡片与背景亮度差 39→68，明显浮起）；light 主题 C_GLASS_BORDER #d7e1f2→#c3d1e9（边框加深可见）
- **卡片加玻璃厚度质感**（make_glass_card）：after(60) 在卡片内部 canvas 画两条柔和明暗带 —— 顶部高光（dark 混白 0.06 / light 混边框色 0.45 ≈ 淡蓝反光线）、底部微暗（混黑 0.025~0.045），模拟磨砂玻璃片的厚度与反光，纯色背景上半透明质感可见
- **light 按钮加强淡彩**：accent 0.14+白 0.05 → 0.18+白 0.03（与白面板差 50→66），hover 变深 0.07 保留
- 验证：py_compile + selftest / test_regress / smoke_gui_test 全绿；PIL 截图确认 dark 卡片明显亮于面板、light 卡片有淡蓝高光与加深边框

## v2.7.9（2026-08-05）按钮去边框锐化 + 全选/全不选图标状态联动 + light 淡彩玻璃

- **修按钮边框锐化**：v2.7.8 加的 1px 高光边框在浅色背景与卡片内仍显锐，去掉（border_width=0），改为玻璃片底色 + 顶部柔和高光条（canvas 画 3px 矩形，mix 白 0.10，x 内缩 6px 避开圆角弧），营造磨砂玻璃顶部反光，全深色主题都能看清
- **修全选/全不选按钮勾勾没变化**：原本 ☑/☐ 是静态装饰，点击后无反馈。新增 `_refresh_sel_buttons()`，按钮图标随全局选中状态联动：
  - 全选按钮：全部选中 → `☑ 全选`（实勾，已是全选态）；否则 → `☐ 全选`
  - 全不选按钮：全部未选 → `☐ 全不选`（已清空）；否则 → `☒ 全不选`（叉框，点击清空）
  - 在 `_set_all` / `_refresh_card_state` / `_add_row` / `start_scan` 清空行时调用
- **light 主题按钮半透明看不出来**：之前按钮 base = mix(面板, accent, 0.08) + 白 0.15 → 几乎纯白（与白面板差 13 亮度），看不出玻璃层次。改为 mix(面板, accent, 0.14) + 白 0.05 → 淡彩玻璃（与白面板差 50+ 亮度），hover 变深（macOS 浅色行为保留）
- **顶部高光条同步**：hover 时随底色提亮自动变亮，disabled 时同步变暗（configure 拦截 state → `_sync_hl`）
- 验证：py_compile + selftest / test_regress / smoke_gui_test 全绿；PIL 截图确认：dark 下按钮明显亮于面板（层差 160+），light 下按钮为可辨识的淡彩玻璃；全选/全不选图标点击后明显切换

## v2.7.8（2026-08-05）修 glass 残留 bug + iOS/macOS 玻璃按钮重做

- **修复 `subprocess is not defined`**：engine.open_in_explorer 用 subprocess 但文件头部漏 import；点击卡片📂后真正调用到此函数立刻 NameError 被弹窗"打开失败"——上轮只补了 app.py 的 import，engine.py 漏补，已加 `import subprocess`
- **背景改为固定不透明**（用户要求后半透明只做在按钮上）：主窗口 + FolderDetail / PackageDetail / SettingsDialog 三个对话框的 `_apply_backdrop` 全部改为纯色背景；彻底移除 `apply_window_backdrop` 调用与 `from glass import ...`（glass.py 保留供将来）
- **GlassButton 视觉重做（iOS 26 / macOS 风格）**：
  - 去掉横贯按钮的顶部反光条 tk.Frame（用户反馈"鼠标放在按键上矩形框住文字"）
  - 真正的根因：CTkButton._on_enter 把文字标签 bg 设成 hover_color，但动画只改 inner_parts，两者不同步 → 文字被一层底色矩形框住。`_apply_look` 现在同步更新 `_text_label` / `_image_label` 的 bg
  - 配色按主题分支：dark 面板下玻璃片向白提亮（比面板明显亮一档，半透明浮起感）；light 面板下玻璃片接近白（accent 0.08 + 白 0.15），hover 变深（macOS 浅色真实行为）
  - 加 1px 细高光边（mix 面板与 C_GLASS_BORDER 0.5），磨砂玻璃边缘
- **卡片网格过渡**：选中边框 `accent × 0.45` 改为 `mix(C_GLASS_BORDER, accent, 0.35)` 柔和化（用户反馈"网格边缘彩色的线条"太花）；`bind_hover` fg_color 加 8 帧平滑过渡动画，不再瞬间跳变
- 验证：py_compile 全过；selftest / test_regress / smoke_gui_test 全绿；PIL ImageGrab 截图确认 dark/light 主题背景不透明、按钮玻璃感、无矩形框住文字

## v2.7.7（2026-08-05）统一按钮规范 + 功能分层 + 修复资源管理器打开无效

- **修复「点击卡片在文件管理器中展开无效」**：主界面卡片「📂」按钮调用 `open_in_explorer`，但 v2.7.0 模块化拆分时 app.py **漏了该导入**，点击即抛 NameError 被静默吞掉、全部无效 —— 已补导入（engine 层函数本身正常）
- **毛玻璃按钮全覆盖**：新增统一玻璃按钮工厂 `glass_btn`（widgets.py），主界面头部「亮色/暗色」、卡片内「📂/📁 查看归属/📦 查看安装包」、全部对话框按钮（清除/全选/反选/全部展开/全部收起/上一页/下一页/关闭/保存/取消）从普通描边 CTkButton 全部换成 GlassButton 玻璃质感
- **统一按钮规范，消灭"拼接感"**：一套规范 4 档 —— 主操作（lg：高 44 圆角 12 14pt 粗体 宽 168）/ 工具栏次级（md：高 44 与主操作完全齐平）/ 对话框（dlg：高 36 圆角 10）/ 卡片内（sm：高 28 圆角 9 自适应宽）；图标+文字一律前置组合，纯文字按钮补齐图标（全选 ☑、全不选 ☐、退出 ⏻）
- **工具栏功能分层**：核心操作（扫描/清理/取消）| 编辑操作（全选/全不选）| 系统操作（设置/退出）三组独立容器；组内间距 8-10px 固定、核心↔编辑组间距 28px 固定、系统组贴右弹性分隔 —— 不再挤成一团或左右甩开
- **GlassButton 增强**：`parent_bg` 参数（卡片内按钮与卡片同底色融合）；disabled 状态同步变暗底色（CTkButton 默认只变暗文字）
- 验证：py_compile 全过；selftest / test_regress 全绿

## v2.7.6（2026-08-05）iOS 玻璃质感全面统一

- **GlassButton 强化**：去掉白色边框（v2.7.5 在浅色背景上变成线框按钮），混合比例 TINT 0.20→0.45、hover_fg 0.55→0.65 → 真正像"面板上浮起的实心玻璃片"
- **工具栏所有按钮统一 GlassButton 玻璃风格**（按用户要求"按键……都是毛玻璃效果"）：扫描（蓝）/清理（橙）/取消（红）/全选（蓝）/全不选（灰）/设置（灰）/退出（红）——全部实心玻璃质感，无线框
- **去掉设置中的"毛玻璃背景"开关**（按用户要求"不要设置毛玻璃选项，直接就是毛玻璃"）：iOS 玻璃质感由 GlassButton 与 make_glass_card 默认承载，不再做窗口级透明
- 验证：截图确认 dark/light 主题下所有按钮都是实心玻璃色块；test_regress/smoke 全绿

## v2.7.5（2026-08-05）修复点击响应 + 设置对话框 + 玻璃按钮可见度

- **修复「多点几次才有反应」**：GlassButton 重写 `_on_enter/_on_leave` 时未调 `super()`，导致 CTkButton 的 `_mouse_inside` 状态得不到维护，`_on_release` 判定为 False 不触发 command——现改为先调 `super()._on_enter(_e)/_on_leave(_e)` 再启动动画，单击 100% 命中、连击每次都生效
- **修复「设置空白页」**：v2.7.1 给 FolderDetail/PackageDetail 加了 `_apply_backdrop` 方法，但 **SettingsDialog 漏了**，且之前一次错误的 Edit 还把它定义错位吞掉了 UI 构建代码——现内联毛玻璃调用、UI 代码回到 `__init__`；截图验证设置对话框完整渲染（回收站/毛玻璃/日志三个卡片 + 保存/取消）
- **修复「半透明效果不明显」**：GlassButton 的 `_base_fg` 改为基于按钮所在面板色 `C_GLASS_2` 混合（而非窗口 `C_BG`，否则与工具栏面板色不匹配看不出层次），混合比例 TINT 提升到 0.35，并加 0.18 透白色的微边框 → 真正像"面板上浮起的玻璃片"
- 验证：Enter 后 `_mouse_inside=True` ✓；单次点击 hits=1、连击 3 次 hits=3 ✓；test_regress/smoke 全绿
- 版本 → v2.7.5

## v2.7.4（2026-08-05）修复玻璃按钮点击无反应

- **修复「点击开始扫描没反应」**：GlassButton 顶部反光条原是 CTkLabel，其内部 canvas 会吞掉鼠标点击（按钮上部约 16px 区域点了没反应）——改用原生 `tk.Frame` + `bindtags` 穿透（点击事件传播到按钮 canvas 触发 command），并让反光条绑定 CTkButton 的 Enter/Leave（维持 `_mouse_inside` 状态，否则 `_on_release` 不会触发命令）
- **修复悬停亮化不生效**：CTkButton 的 hover 变色通过 canvas `inner_parts` item 实现（非 `fg_color` 属性），动画改为直接更新 `inner_parts`，悬停时按钮背景真实变亮
- 验证：真实鼠标事件（win32）点击反光条区域 0→1 次命中；event_generate 完整点击流命中；test_regress / smoke_gui_test 全绿
- 版本 → v2.7.4

## v2.7.3（2026-08-04）玻璃按钮 + 背景恢复不透明

- **新增 iOS 风格玻璃按钮（GlassButton）**：半透明底色（以窗口背景为主混入强调色）+ 悬停顶部反光动画（背景平滑变亮 + 白色高光条逐渐显现，约 110ms 过渡，Enter/Leave 双向平滑）——「开始扫描」「清理选中」两个主按钮已启用
- **窗口背景恢复不透明**：按用户需求「背景不变」，`glass_mode` 默认改为关闭（设置里仍可手动开启窗口级毛玻璃）；同步重置了本机 settings.json 中的旧值
- 技术：`GlassButton` 位于 widgets.py（CTkButton 子类，禁用默认 hover 突变由动画接管；反光条用白色混合色模拟高光，兼容明暗主题）
- 版本 → v2.7.3；测试全绿（test_regress / smoke_gui_test），反光动画进度验证 _t=1.0

## v2.7.2（2026-08-04）毛玻璃可见性修复

- **两个根因 bug**（导致 v2.7.1 用户看到"没什么变化"）：
  1. Tk `winfo_id()` 返回内部子窗口句柄，DWM/WCA 需要顶层 HWND——新增 `_top_hwnd()` 用 `GetAncestor(winfo_id(), GA_ROOT)` 取真正顶层；验证 DwmSetWindowAttribute 之前返回 E_HANDLE（0x80070006），现在返回 0（成功）
  2. `make_window_transparent` 用 `configure(fg_color=)` 仅 customtkinter 支持，原生 tk Toplevel 抛 TclError 被吞导致透明色没设上——改为先试 `fg_color` 再 fallback `bg`
- 用 PIL ImageGrab + 鲜艳色块画布做可视化验证：确认窗口背景**真的半透明**（能看到背后应用/桌面），满足"看到软件后面应用的背景颜色"需求
- 版本 → v2.7.2；测试全绿（selftest / test_regress / smoke_gui_test），exe 13.84MB 重新打包覆盖

## v2.7.1（2026-08-04）毛玻璃重构 + 图标修复 + 移除粒子

- **修复真实应用图标消失**：v2.7.0 拆分时 app.py 漏 `import tkinter as tk`，图标线程中 `tk.PhotoImage` 抛 NameError 被吞，导致卡片永远只显示字符图标 —— 已修复，应用图标恢复显示
- **移除粒子特效**：主窗口与全部对话框不再创建粒子背景（滚动节流路由、按钮爆发、完成庆祝一并移除）；`particles.py` 保留供性能测试（`tests/test_perf_features.py` 仍 ALL_PASS）
- **真毛玻璃（iOS 风格半透明）**：新增 `glass.py`，用系统级 Acrylic/Mica 实现——窗口背景设为透明键色 + `DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE)`（Win11）/ `SetWindowCompositionAttribute`（Win10）模糊窗口背后的应用，配合色调叠加，可隐约看到背后内容（类 iOS 毛玻璃）
  - 主窗口与文件夹归属 / 安装包 / 设置对话框全部应用
  - 设置新增「毛玻璃背景」开关（`glass_mode`，默认开，持久化到 settings.json）；系统不支持或关闭时自动回退纯色背景
  - 主题切换时按当前主题色调重新应用
- 版本迁至 `config.py` VERSION = "v2.7.1"；测试全绿（selftest / test_regress / smoke_gui_test / test_perf_features）

## v2.7.0（2026-08-04）模块化重构 + 目录整理

- **模块化拆分**：3646 行单文件 `main.py` 按职责拆为 8 个模块 + 薄入口：
  - `config.py`（常量/主题/路径/用户设置/日志）、`rules.py`（垃圾分类/规则构建）、`engine.py`（扫描/清理引擎，无 GUI 依赖可独立测试）、`icons.py`（图标提取）、`particles.py`（动画内核）、`widgets.py`（通用 UI 部件）、`dialogs.py`（详情/设置对话框）、`app.py`（主窗口）
  - 颜色常量改为动态 `config.C_*` 访问：主题切换时 `apply_theme` 更新 config 全局，所有模块即时生效（配合重建 UI）
  - `main.py` 保留为启动入口 + 测试兼容导出（`python main.py` 与既有测试脚本无需改动）
- **目录整理**：测试脚本统一移入 `tests/`（selftest/回归/性能/冒烟，均已加项目根 sys.path 引导）；图标生成脚本移入 `tools/`；README 目录结构与「自定义与迭代」同步更新
- **验证**：py_compile 全过；selftest / test_regress / test_perf_features（ALL_PASS）/ smoke_gui_test（含明暗主题切换）全绿；PyInstaller 打包验证 8 模块全部进入 PYZ
- 版本号迁至 `config.py`（VERSION = "v2.7.0"）

## v2.6.0（2026-08-04）安全 + 体验增强

- 删除到回收站（可恢复）模式：设置中可开关（默认永久删除），开启后清理经 `SHFileOperationW(FOF_ALLOWUNDO)` 删除进回收站、误删可恢复（按父目录分组批量调用摊薄开销）；清理确认框按模式给出不同风险提示
- 扫描/清理可中途取消：工具栏新增「✕ 取消」按钮（运行中启用），协作式取消（`threading.Event`），最快在下一个检查点生效；取消扫描保留已扫结果，取消清理展示已释放部分且不自动重扫
- 日志：记录扫描/清理结果与每个删除失败文件的路径（`%LocalAppData%\C盘清理工具\cleaner.log`），便于排查与报 bug
- 设置持久化：回收站模式与主题偏好保存到 `settings.json`，重启不丢；工具栏新增「⚙ 设置」入口（回收站开关 + 日志路径说明）
- 技术：`scan_*` 扫描函数与 `clean_files` 新增可选 `cancel_check` 参数（默认 None，向后兼容 selftest）；`_set_controls` 对取消按钮反向管理

## v2.5.3（2026-08-04）代码审查 bug 修复

- 修复「缩略图缓存」等非递归规则永远扫不到文件：`scan_path_rule` 的 pattern 匹配原为 `startswith(pat.replace("*",""))`，对 `thumbcache_*.db` 会退化成前缀 `thumbcache_.db`，真实文件名 `thumbcache_256.db` 不匹配 → 改用标准 `fnmatch` 通配符匹配
- 删除重复的 `_detect_refresh_rate` 定义（旧版依赖 Python 3.13 已移除的 `ctypes.wintypes.DEVMODEW`，属死代码，被新版静默覆盖）
- 修复真实应用图标「异步加载」名不副实：原实现线程只做 `after(0,...)` 调度，真正的图标提取（LoadLibrary + GetDIBits + zlib 编码）仍在主线程执行，首次扫描会卡 UI —— 改为 worker 线程完成提取，主线程仅创建 PhotoImage 并更新徽章
- 补齐关闭守卫：`_scan_worker` / `_clean_worker` 循环与 `_finish_scan` / `_finish_clean` 在窗口关闭后不再操作已销毁控件（与 `_sync_main_selection` 行为一致）

## v2.5.2（2026-08-03）图标清晰度 + 滚动体验再优化

- 系统类内置图标全面改用矢量 SVG 源：从 npm @tabler/icons 下载并以 sharp 栅格化为 64px 透明 PNG，统一强调色 #60a5fa 描边，零锯齿（消除 cleanmgr 32px 源上采样的「图标模糊」问题）。语义映射：win_temp/user_temp → brush（清扫刷）、prefetch → gauge（仪表）、wsus → download、delivery → package、wer → alert-triangle、winlogs → file-text、crashdumps → bug、recycle → recycle、thumb → photo；SVG 源文件保存在 `icons/svg/` 便于日后换色/换风格
- 滚动割裂感彻底修复：滚动期间完全停止背景粒子渲染（之前是每 4 帧渲染一次），调度间隔降到 33ms（~30fps tick，仅统计不渲染），把主循环全部让给滚动事件
- 删除过时的 make_system_icons.py（已被 SVG 路径取代）

## v2.5.1（2026-08-03）日常体验打磨

- 修复显示器刷新率探测：原实现依赖 `ctypes.wintypes.DEVMODEW`（Python 3.13 已移除）静默失败，导致 165Hz 显示器永远被识别为 60Hz —— 改为手工定义结构体，立即返回真实刷新率
- 默认主题切换为日间模式（按用户偏好）
- 解决快速上下滑动割裂感：全局鼠标滚轮路由到当前窗口背景动画，滚动期（250ms）内背景仅每 4 帧渲染一次（165Hz→41fps），把主循环让出给滚动
- 系统类内置图标重生：从 cleanmgr.exe（32px 资源）以 LANCZOS 重缩到 64px；recycle/thumb 改用 shell32/imageres 256 PNG 矢量 → 64 LANCZOS
- 运行时图标提取升级：`extract_app_icon_png` 默认 64，优先 LoadLibrary+LoadImage 取指定尺寸原生资源，缩放改双线性（消除最近邻的锯齿与块感），保留 ExtractIconExW 回退
- `--perf` 叠加层配色改为跟随主题

## v2.5.0（2026-08-03）165Hz 高性能渲染优化

- 移除 30fps 固定上限：自动探测显示器刷新率并以之为目标帧率（上限 165Hz），perf_counter 精确帧节拍 + 绝对相位自修正，无累积漂移
- 帧率无关物理：粒子/爆发速度改为 px/s 时间基准，任意帧率下动画速度恒定
- 渲染内核重写：平行数组 + sin 查找表 + 量化脏重绘（仅像素级变化才更新 canvas，高帧率下 Tk 脏区缩小 90%+），爆发粒子对象池复用（消除每帧 create/delete）
- 自适应画质看门狗：帧耗时持续超预算自动降粒子（46→12 下限）、有裕量自动恢复，低配机器不掉帧；窗口最小化/不可见时自动降到 5fps 省 CPU
- Windows 定时器精度提升（timeBeginPeriod(1)），after() 可稳定到 6.06ms
- 内置 FPS 表 + `--perf` 叠加层；`--fps N` 手动覆盖目标帧率

## v2.4.4（2026-08-03）代码审查修复

- Bug 修复：二级选择过滤按路径匹配时未做大小写归一化，Windows 下盘符/目录大小写不一致（C:\App vs c:\app）会导致选中文件夹的文件被漏清 —— 新增 `_normcase` 统一比较
- 健壮性：主窗口关闭时标记 `_closing`，避免关闭流程中二次联动操作已清空的控件；图标异步加载前检查控件是否仍存在（winfo_exists），消除主题切换竞态噪音

## v2.4.3（2026-08-03）图标内置打包，跨机器可用

- 图标不再依赖本机安装路径：28 类应用/系统图标（Chrome/Edge/微信/Steam/NVIDIA/回收站等）已下载并打包进 exe，任何电脑运行都显示真实图标（之前按本机 exe 路径提取，换机失效）
- 图标来源：simple-icons 官方品牌 SVG（sharp 转换 64x64 透明 PNG）+ DuckDuckGo favicon + Adobe 官网 favicon + Windows shell32.dll/cleanmgr.exe 系统图标
- 加载策略：优先读 exe 内置 icons/ 资源（sys._MEIPASS），未内置才回退本机提取
- 打包：build.bat 已加 `--add-data "icons;icons"`
- 聚合类（深度扫描 / 安装包）仍保留类别字符图标

## v2.4.2（2026-08-03）图标覆盖补全 + 双向联动修正

- Bug 修复：二级详情「取消全选」后主菜单取消勾选，但「再次全选」时主菜单未恢复 —— 改为双向同步：全取消取消勾选 / 有选中恢复勾选
- 图标补全：系统类清理项（临时文件/回收站/更新缓存/错误报告等）使用 Windows 自带工具图标（cleanmgr.exe / shell32.dll 索引），NVIDIA/AMD/Intel 着色器缓存使用显卡控制软件图标；dll 图标索引候选支持「路径:索引」语法
- 真实应用图标仍仅对已安装应用生效，未安装的应用保留原类别字符图标

## v2.4.1（2026-08-03）二级选择联动 + 真实应用图标

- Bug 修复：二级详情（文件夹归属 / 软件更新安装包）中取消全选后，主菜单对应清理项的勾选状态联动取消，避免「主菜单仍勾选但实际无文件可清理」的状态不一致
- 新功能：主菜单清理项卡片显示真实应用图标（从已安装应用 exe 提取，如 Chrome/Edge/微信/Steam 等；未安装的应用保留原类别字符图标）。纯标准库实现（Shell32 + GetDIBits + PNG 自编码），不引入 PIL，打包体积不变
- 图标异步加载：后台线程提取编码，主线程更新 UI，扫描不卡顿

## v2.4.0（2026-08-03）GUI 视觉重构

- 清理项卡片全面重做：更大圆角 + 图标徽章淡色底 + 分类胶囊徽章 + 选中态高亮边框（勾选后卡片边框随类别强调色点亮）
- 头部重做：应用图标徽章 + 版本徽章 + 双统计卡（已发现垃圾文件 / 预计可释放）
- 工具栏：毛玻璃面板化 + 主操作按钮放大圆润 + 分隔线区分主/辅操作
- 状态栏：进度百分比实时显示 + 更精的进度条与状态文案
- 空状态指引卡与详情对话框（文件夹归属 / 安装包）同步美化，风格全应用统一
- 技术：新增 `_mix_color` 颜色混合工具（生成淡色底徽章）、`_refresh_card_state` 选中态同步、`_set_progress` 统一进度更新入口

## v2.3.4（2026-08-03）GUI 体验优化

- Bug 修复：响应式列数统一为 340px 目标列宽 / 1-4 列自适应（原注释与实现不一致）；详情对话框标题区改为左标题+副标题两行布局，修复窄窗错位；路径/描述文本 wraplength 随窗口与列宽动态更新，修复溢出；主窗口关闭协议（停止粒子循环）；扫描/清理中禁用退出；相同详情对话框不再重复打开（已打开则置顶）；主题切换自动关闭旧配色对话框
- 美化：状态栏毛玻璃面板 + 状态指示灯；空状态垂直居中 + 三步指引卡片；清理项卡片图标圆形徽章 + 加大详情按钮点击区；对话框搜索区拆两行
- 交互：清理项卡片整体点击切换勾选（hand2 光标）；扫描/清理实时显示当前项进度 (i/n)；对话框搜索框自动聚焦 + ESC 关闭；主窗口 Enter 快捷扫描

## v2.3.2（2026-07-25）二级目录选择 + 资源管理器打开

- 二级目录选择：在「第三方应用深度清理」和「软件更新安装包」详情对话框中，每个文件夹/安装包均可勾选/取消，与一级目录选择行为一致（含全选/反选、默认全选、清理时仅清理选中项）
- 资源管理器打开：每个清理项（一级与二级）操作区新增「📂 打开」按钮，点击后在文件资源管理器中定位并打开对应文件/文件夹路径（文件夹直接打开目录，文件用 `explorer /select,` 定位）
- 清理确认与统计按二级选择精确计算文件数与可释放空间

## v2.3.1（2026-07-25）新增软件更新安装包清理

- 新增「软件更新安装包」扫描模块：识别各软件在 AppData/ProgramData 中下载的更新安装包（.exe / .msi / .msu / .cab / .msp），排除 <1MB 的小文件避免误报
- 按软件来源分组，提供可展开/收起的详情对话框，查看每个安装包的：软件来源名 / 安装包文件名 / 版本号 / 大小 / 路径
- 版本号从文件名自动解析（正则匹配 x.y.z 形式）
- 交互方式与「第三方应用深度清理」完全一致：主界面卡片 + 「📦 查看安装包」按钮 + 毛玻璃对话框；复用分页 + 搜索 + 异步渲染 + 轻量粒子背景

## v2.3.0（2026-07-23）UI 视觉重做

- 全新视觉系统：深邃渐变背景 + 毛玻璃风格卡片 + 现代化字体层级与配色
- 新增动画粒子背景层（Canvas 实现，~46 个发光粒子缓慢上浮 + 闪烁）
- 新增交互反馈粒子爆发：点击「扫描垃圾」/「清理选中」时从按钮位置迸射粒子
- 卡片采用毛玻璃质感（柔和边框 + 悬停高亮 + 大圆角），整体更现代精致
- 性能保障：粒子数量上限 + coords 原地更新（非 delete/recreate），30fps 单循环，扫描/清理仍在子线程，UI 不卡顿

## v2.2.2（2026-07-23）

- 压缩主界面清理项卡片高度：改 grid sticky 为 ew，缩小内边距，告别卡片下方空白

## v2.2.1（2026-07-23）

- 主界面清理项改为一行两个的网格布局，节省纵向空间
- 新增应用图标：蓝白 C 配绿色闪光徽章（见 app_icon.svg / app_icon.ico）

## v2.2.0（2026-07-19）

- 重做 UI 视觉与排版：微软雅黑 UI 字体、卡片化布局、统一配色与间距
- 移除原「系统+第三方应用 激进清理」说明文字，头部更简洁
- 「查看文件夹归属」对话框改为分页 + 搜索 + 异步渲染，解决文件夹过多时的卡顿
- 文件夹归属新增垃圾类型分类徽章（缓存 / 临时 / 日志 / 崩溃转储 / Service Worker 等）
