@echo off
chcp 65001 >nul
title 野猪检测工具 - 一键打包
cd /d "%~dp0"

echo ============================================
echo   野猪检测工具 · 一键打包（技术员用）
echo   Boar Detector - One-click Build
echo ============================================
echo   打包完成后，双击「安装到桌面.bat」即可给电脑装好
echo.

REM ---------- [1/3] 检查 / 静默安装 Python ----------
echo [1/3] 检查 Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo       未检测到 Python，正在静默安装 Python 3.10（约 30MB）...
    powershell -Command "Invoke-WebRequest -Uri 'https://mirrors.tuna.tsinghua.edu.cn/python/3.10.11/python-3.10.11-amd64.exe' -OutFile '%TEMP%\py310.exe' -UseBasicParsing" >nul 2>&1
    if not exist "%TEMP%\py310.exe" (
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe' -OutFile '%TEMP%\py310.exe' -UseBasicParsing" >nul 2>&1
    )
    if not exist "%TEMP%\py310.exe" (
        echo   [FAIL] Python 下载失败，请手动安装:
        echo          https://www.python.org/downloads/windows/
        echo         安装时务必勾选「Add python.exe to PATH」
        pause & exit /b 1
    )
    echo       正在安装（静默，约 1 分钟）...
    start /wait "" "%TEMP%\py310.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    if exist "C:\Program Files\Python310\python.exe" (
        set PYTHON=C:\Program Files\Python310\python.exe
    ) else if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
        set PYTHON=%LocalAppData%\Programs\Python\Python310\python.exe
    ) else (
        echo   [FAIL] Python 安装后未找到，请重新运行本脚本或手动安装
        pause & exit /b 1
    )
) else (
    set PYTHON=python
)
echo   [OK] Python 就绪: %PYTHON%
echo.

REM ---------- [2/3] 安装依赖 ----------
echo [2/3] 安装依赖（onnxruntime / opencv / pyinstaller）...
%PYTHON% -m pip install pyinstaller onnxruntime opencv-python-headless numpy Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo       清华源失败，改用默认源重试...
    %PYTHON% -m pip install pyinstaller onnxruntime opencv-python-headless numpy Pillow
    if errorlevel 1 (
        echo   [FAIL] 依赖安装失败，请检查网络
        pause & exit /b 1
    )
)
echo   [OK] 依赖就绪
echo.

REM ---------- [3/3] 打包 exe ----------
echo [3/3] 打包 BoarDetector.exe（1-2 分钟）...
cd /d "%~dp0\..\boar_ui"
%PYTHON% -m PyInstaller --onefile --windowed --name "BoarDetector" --icon "boar.ico" --add-data "model\best.onnx;model" --hidden-import cv2 --hidden-import numpy --hidden-import onnxruntime --hidden-import PIL --clean --noconfirm src\app.py
cd /d "%~dp0"
echo.
if exist "..\boar_ui\dist\BoarDetector.exe" (
    copy /y "..\boar_ui\dist\BoarDetector.exe" "%~dp0BoarDetector.exe" >nul
    echo ============================================
    echo   ✅ 打包成功！
    echo   程序已生成:  %~dp0BoarDetector.exe
    echo.
    echo   下一步: 双击「安装到桌面.bat」在桌面建快捷方式
    echo ============================================
) else (
    echo ============================================
    echo   ❌ 打包失败，请往上翻看报错信息
    echo ============================================
)
pause
