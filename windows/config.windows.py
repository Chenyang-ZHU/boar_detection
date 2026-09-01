"""野猪检测服务配置（Windows EXE 版）"""

import sys
import os


def _base():
    """PyInstaller 打包后数据在 _MEIPASS；源码运行时在服务目录"""
    if getattr(sys, '_MEIPASS', None):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _base()

# 服务端口
PORT = 5000

# 服务主机
HOST = "0.0.0.0"

# 模型路径（EXE 同目录 / 打包内置的 best.pt）
MODEL_PATH = os.path.join(BASE_DIR, "best.pt")

# 推理设备（Windows 用 CPU）
DEVICE = "cpu"

# 置信度阈值
CONFIDENCE_THRESHOLD = 0.45

# NMS IoU 阈值
IOU_THRESHOLD = 0.45

# 模型推理输入尺寸
INPUT_SIZE = 640

# ---------- 图像处理（接受任意尺寸，按原尺寸处理并返回） ----------
IMAGE_HARD_LIMIT_SIDE = 8192
IMAGE_MAX_FILE_BYTES = 50 * 1024 * 1024

# ---------- 视频处理 ----------
VIDEO_MAX_DURATION = 300
VIDEO_MAX_SIZE = 500 * 1024 * 1024
VIDEO_CODEC = "auto"

# ---------- 健壮性配置 ----------
MAX_INFERENCE_WORKERS = 4
WAITRESS_THREADS = 16
IMAGE_PROCESS_TIMEOUT = 30
VIDEO_PROCESS_TIMEOUT = 180

# 日志级别
LOG_LEVEL = "INFO"
