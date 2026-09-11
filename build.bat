@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  C盘清理工具 - 一键打包脚本 (by zx)
REM  双击本文件即可重新生成 exe 到当前目录（所有打包命令都在本文件）
REM  依赖：customtkinter + pyinstaller（miniconda 环境已装）
REM  若打包后无反应，请用管理员身份运行
REM ============================================================

REM ---- 1. 定位 PyInstaller（必须用带 tkinter 的环境）----
REM  注意：WorkBuddy venv 精简版无 tkinter，用它打包的 exe 运行时会
REM  ModuleNotFoundError 崩溃 —— 因此只用 miniconda（含 tkinter），
REM  找不到则回退 PATH 里的 pyinstaller 并提示检查环境
REM  miniconda 可能装在 D:\ 或 E:\（本机现为 E:\miniconda3）
set "PY="
if exist "E:\miniconda3\Scripts\pyinstaller.exe" set "PY=E:\miniconda3\Scripts\pyinstaller.exe"
if not defined PY if exist "D:\miniconda3\Scripts\pyinstaller.exe" set "PY=D:\miniconda3\Scripts\pyinstaller.exe"
if not defined PY set "PY=pyinstaller"

rem 校验可用性：绝对路径用 if exist（where 对带引号的绝对路径会误判失败）；
rem PATH 命令名才用 where
if exist "%PY%" goto :py_ok
where %PY% >nul 2>nul
if not errorlevel 1 goto :py_ok
echo [错误] 未找到 PyInstaller（%PY%），请先执行: pip install pyinstaller
pause
exit /b 1
:py_ok
if "%PY%"=="pyinstaller" (
  echo [提示] 使用 PATH 中的 pyinstaller，请确认其 Python 环境带 tkinter
)
echo [1/3] 使用 PyInstaller: %PY%

REM ---- 2. 打包（onefile + UAC 提权 + 内置图标 + 排除 PIL）----
REM  main.py 顶层导入 config/theme/rules/engine/widgets/dialogs/app，
REM  均在项目根目录，PyInstaller 自动跟随，无需 --paths。
echo [2/3] 开始打包...
REM 误报说明：--noupx（UPX 加壳是杀软启发式的重灾区，体积换信任）；
REM  --version-file 写入公司/产品/版本号元数据（无元数据的裸 exe 更易被 ML 误判）。
REM  若仍被报毒，属 PyInstaller 通用误报，见 README「报毒说明」节。
"%PY%" --onefile --windowed --uac-admin --noupx --clean --name "C盘清理工具" --icon "app_icon.ico" --version-file "version_info.txt" --hidden-import customtkinter --hidden-import darkdetect --exclude-module PIL --exclude-module Pillow --exclude-module numpy --exclude-module matplotlib --add-data "icons;icons" --distpath "dist" --workpath "build" --specpath "." --noconfirm "main.py"
if errorlevel 1 (
  echo [失败] 打包出错，请查看上方报错信息。
  pause
  exit /b 1
)

REM ---- 3. 复制到根目录并验证 ----
if exist "dist\C盘清理工具.exe" (
  copy /Y "dist\C盘清理工具.exe" "C盘清理工具.exe" >nul
  for %%A in ("C盘清理工具.exe") do (
    echo [完成] 已生成 C盘清理工具.exe ^(%%~zA 字节^)，位于本文件夹
  )
  echo 运行: 双击 C盘清理工具.exe 即可（请求管理员权限时请点「是」）
) else (
  echo [失败] 未生成 exe，请检查上方报错信息。
)
pause
