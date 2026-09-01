@echo on
cd /d "%~dp0"
echo Current dir: %cd%
echo.
echo Python:
python --version
echo.
echo Installing pip packages...
python -m pip install pyinstaller onnxruntime opencv-python-headless numpy Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
echo Building exe...
python -m PyInstaller --onefile --windowed --name "BoarDetector" --add-data "model\best.onnx;model" --hidden-import cv2 --hidden-import numpy --hidden-import onnxruntime --hidden-import PIL --clean --noconfirm src\app.py
echo.
echo Exit code: %errorlevel%
if exist "dist\BoarDetector.exe" (
    echo SUCCESS
) else (
    echo FAILED
)
echo.
echo Press Ctrl+C to close, or wait...
pause
