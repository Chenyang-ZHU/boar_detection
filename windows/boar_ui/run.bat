@echo off
cd /d "%~dp0"
python -m pip install onnxruntime opencv-python-headless numpy Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
python src\app.py
pause
