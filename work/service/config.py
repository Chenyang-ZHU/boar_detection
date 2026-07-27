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

# 输入图片尺寸（固定 640×640）
INPUT_SIZE = 640

# 最大同时推理线程数（Flask 多线程请求时的限制）
MAX_INFERENCE_WORKERS = 4

# 日志级别
LOG_LEVEL = "INFO"
