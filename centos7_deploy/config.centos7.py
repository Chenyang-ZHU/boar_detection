"""野猪检测服务配置（CentOS 7 CPU 部署版）"""

import os

# 服务端口
PORT = 5000

# 服务主机
HOST = "0.0.0.0"

# 模型路径（绝对路径，部署在 /opt/boar-detection）
MODEL_PATH = "/opt/boar-detection/best.pt"

# 推理设备（CentOS 7 无 GPU，用 CPU）
DEVICE = "cpu"

# 置信度阈值（2026-08-30 调优：0.25→0.45，误检率从 20% 降到 12.9%，召回仍 97%）
CONFIDENCE_THRESHOLD = 0.45

# NMS IoU 阈值
IOU_THRESHOLD = 0.45

# 模型推理输入尺寸
INPUT_SIZE = 640

# ---------- 图像处理（接受任意尺寸，按原尺寸处理并返回） ----------
# 图片长边超过此值不处理，返回说明（含原始尺寸）
IMAGE_HARD_LIMIT_SIDE = 8192
# 图片文件大小上限（字节），超过返回说明
IMAGE_MAX_FILE_BYTES = 50 * 1024 * 1024

# ---------- 视频处理（接受任意尺寸/时长，按原尺寸处理并返回） ----------
# 视频最大时长（秒），超过返回说明（含原始信息）
VIDEO_MAX_DURATION = 300
# 视频文件大小上限（字节），超过返回说明
VIDEO_MAX_SIZE = 500 * 1024 * 1024
# 视频编码策略："auto" 自动选择（优先 H.264，回退 mp4v）/ "mp4v" / "avc1"
VIDEO_CODEC = "auto"

# ---------- 健壮性配置 ----------
# 最大同时处理的请求数（信号量限流，满员返回 429001 繁忙）
MAX_INFERENCE_WORKERS = 4
# waitress 服务器线程数（并发连接上限，比信号量宽裕）
WAITRESS_THREADS = 16
# 图像单请求处理超时（秒），超时返回 50002
IMAGE_PROCESS_TIMEOUT = 30
# 视频单请求处理超时（秒），超时返回 50002
VIDEO_PROCESS_TIMEOUT = 180

# 日志级别
LOG_LEVEL = "INFO"
