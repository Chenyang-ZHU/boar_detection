@echo off
chcp 65001 >nul
REM ============================================================
REM  野猪检测服务 · Windows 傻瓜 EXE 构建脚本
REM  Build a standalone Windows EXE (no Python needed on target)
REM
REM  用法 / Usage:
REM     在 windows\ 目录下双击本文件（或命令行运行）
REM     Double-click this file in the windows\ folder
REM
REM  前提 / Prerequisites (ONCE on the build machine):
REM     装 Python 3.10  https://www.python.org/downloads/
REM     (安装时勾选 "Add Python to PATH")
REM
REM  产物 / Output:
REM     dist\野猪检测服务.exe  —— 复制到任何 Windows 双击即运行
REM ============================================================

cd /d "%~dp0"

echo ======================================
echo   野猪检测服务 · Windows EXE 构建
echo ======================================

REM ---------- 1. 检查 Python ----------
where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 Python。请先安装 Python 3.10 并勾选 Add to PATH。
  echo [Error] Python not found. Install Python 3.10 first.
  pause
  exit /b 1
)
echo Python:
python --version

REM ---------- 2. 安装依赖（首次较慢） ----------
echo.
echo [2/4] 安装依赖 / Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install ultralytics waitress imageio-ffmpeg qtfaststart flask pyinstaller

REM ---------- 3. 用 Windows 配置覆盖（构建后自动恢复） ----------
echo.
echo [3/4] 应用 Windows 配置 / Applying Windows config...
set "CFG=..\work\service\config.py"
copy /Y "%CFG%" "%CFG%.bak" >nul
copy /Y config.windows.py "%CFG%" >nul

REM ---------- 4. 构建 EXE ----------
echo.
echo [4/4] 构建 EXE（约 5-15 分钟）/ Building EXE (~5-15 min)...
python -m PyInstaller --clean --noconfirm boar_detection.spec

REM ---------- 恢复配置 ----------
copy /Y "%CFG%.bak" "%CFG%" >nul
del "%CFG%.bak" >nul

echo.
echo ======================================
if exist "dist\野猪检测服务.exe" (
  echo  构建完成！
  echo  产物：dist\野猪检测服务.exe
  echo  把这个 exe 拷到任何 Windows，双击即可运行（无需安装任何东西）
  echo.
  echo  运行后访问: http://127.0.0.1:5000
  echo  Build OK! Output: dist\野猪检测服务.exe
) else (
  echo [错误] 构建失败，请把屏幕输出发给技术人员。
  echo [Error] Build failed, contact technical support.
)
echo ======================================
pause
