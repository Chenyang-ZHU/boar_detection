"""野猪检测服务配置"""

import os

# 服务端口
PORT = 5000

# 服务主机
HOST = "0.0.0.0"

# 模型路径（相对于本项目根目录，也支持绝对路径）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(BASE_DIR, "work", "runs", "detect", "boar_detection", "yolov8n_merged_final", "weights", "best.pt")

# 推理设备（"cpu" 或 "cuda:0"，设为 None 则自动选择）
DEVICE = None  # 自动检测 GPU，无 GPU 则用 CPU

# 置信度阈值（低于此值的检测结果将被过滤）
CONFIDENCE_THRESHOLD = 0.25

# NMS IoU 阈值
IOU_THRESHOLD = 0.45

# 模型推理输入尺寸（YOLO 内部会自动缩放）
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
