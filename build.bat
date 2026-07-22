@echo off
chcp 65001 >nul
REM ============================================================
REM  C盘清理工具 - 一键打包脚本 (by zx)
REM  使用方法：双击本文件即可重新生成 exe 到当前目录
REM  前提：已安装 Python 3.10+，且执行过  pip install customtkinter pyinstaller
REM ============================================================
setlocal

REM 默认使用 WorkBuddy 自带 Python 虚拟环境中的 pyinstaller；
REM 若未安装该环境，可改回 set PY=pyinstaller（需自行 pip install pyinstaller customtkinter）
set PY="C:/Users/zx/.workbuddy/binaries/python/envs/default/Scripts/pyinstaller.exe"
if not exist %PY% set PY=pyinstaller

%PY% --onefile --windowed --uac-admin --name "C盘清理工具" ^
  --icon "app_icon.ico" ^
  --hidden-import customtkinter --hidden-import darkdetect ^
  --exclude-module PIL --exclude-module Pillow ^
  --distpath "dist" --workpath "build" --specpath "." ^
  "main.py"

if exist "dist\C盘清理工具.exe" (
  copy /Y "dist\C盘清理工具.exe" "C盘清理工具.exe" >nul
  echo.
  echo [完成] 已生成 C盘清理工具.exe（位于本文件夹，请手动复制到桌面）
) else (
  echo [失败] 未生成 exe，请检查上方报错信息。
)
pause
