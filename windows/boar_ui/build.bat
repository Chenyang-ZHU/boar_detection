@echo off
cd /d "%~dp0"
echo ============================================
echo   Boar Detector - One Click Build
echo ============================================

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [1/3] Python not found. Downloading...
    echo       Please wait...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe' -OutFile '%TEMP%\python-installer.exe' -UseBasicParsing" >nul 2>&1
    if errorlevel 1 (
        powershell -Command "Invoke-WebRequest -Uri 'https://mirrors.tuna.tsinghua.edu.cn/python/3.10.11/python-3.10.11-amd64.exe' -OutFile '%TEMP%\python-installer.exe' -UseBasicParsing" >nul 2>&1
    )
    if not exist "%TEMP%\python-installer.exe" (
        echo [FAIL] Download failed. Install Python manually.
        echo        https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
        pause & exit /b 1
    )
    echo       Installing Python (silent)...
    start /wait "" "%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    if exist "C:\Program Files\Python310\python.exe" (
        set PYTHON=C:\Program Files\Python310\python.exe
    ) else if exist "C:\Python310\python.exe" (
        set PYTHON=C:\Python310\python.exe
    ) else (
        echo [FAIL] Python not found after install
        pause & exit /b 1
    )
) else (
    set PYTHON=python
)
echo [OK] Python ready
echo.

REM --- Install packages ---
echo [2/3] Installing packages...
%PYTHON% -m pip install pyinstaller onnxruntime opencv-python-headless numpy Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [FAIL] Package install failed, retry without mirror...
    %PYTHON% -m pip install pyinstaller onnxruntime opencv-python-headless numpy Pillow
    if errorlevel 1 (
        echo [FAIL] Package install failed, check internet
        pause & exit /b 1
    )
)
echo [OK] Packages ready
echo.

REM --- Build exe ---
echo [3/3] Building BoarDetector.exe...
echo       This may take 1-2 minutes...
%PYTHON% -m PyInstaller --onefile --windowed --name "BoarDetector" --add-data "model\best.onnx;model" --hidden-import cv2 --hidden-import numpy --hidden-import onnxruntime --hidden-import PIL --clean --noconfirm src\app.py
echo.
if exist "dist\BoarDetector.exe" (
    echo ============================================
    echo   SUCCESS!
    echo   Output: dist\BoarDetector.exe
    echo   Double-click to run
    echo ============================================
) else (
    echo ============================================
    echo   FAILED - Scroll up to see error messages
    echo ============================================
)
pause
