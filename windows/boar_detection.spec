# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# PyInstaller spec - 生成 Windows 傻瓜 EXE
# Build a standalone Windows EXE (no Python needed on target)
#
# 在 Windows 上运行（见 build_exe.bat）：
#     pyinstaller boar_detection.spec
# 产物：dist\野猪检测服务.exe （双击即运行）
# ============================================================

import os
import sys
import imageio_ffmpeg

# ---------- 路径 / Paths ----------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), '..'))
SERVICE_DIR = os.path.join(PROJECT_ROOT, 'work', 'service')
MODEL = os.path.join(PROJECT_ROOT, 'work', 'runs', 'detect', 'boar_detection',
                     'yolov8n_merged_final', 'weights', 'best.pt')
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()   # imageio-ffmpeg 内置 ffmpeg 路径

# ---------- 打包的数据文件 / Bundled data ----------
datas = [
    (MODEL, '.'),
    (os.path.dirname(FFMPEG_EXE), 'imageio_ffmpeg/binaries'),  # ffmpeg 二进制
]

# ---------- ultralytics/torch 的隐藏依赖 ----------
hiddenimports = [
    'ultralytics',
    'ultralytics.nn.modules',
    'ultralytics.utils',
    'ultralytics.utils.tal',
    'ultralytics.utils.loss',
    'ultralytics.utils.metrics',
    'ultralytics.data',
    'ultralytics.data.build',
    'ultralytics.engine',
    'ultralytics.engine.model',
    'ultralytics.models',
    'ultralytics.models.yolo',
    'ultralytics.models.yolo.detect',
    'torch',
    'torchvision',
    'cv2',
    'waitress',
    'qtfaststart',
    'imageio_ffmpeg',
    'numpy',
    'PIL',
    'flask',
]

# ---------- spec ----------
a = Analysis(
    [os.path.join(SERVICE_DIR, 'app.py')],
    pathex=[SERVICE_DIR, os.path.dirname(SERVICE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pandas', 'seaborn', 'scipy'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='野猪检测服务',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # 显示控制台窗口（可看到日志）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
