"""模型加载与推理封装"""

import time
import logging
import threading
from io import BytesIO

import numpy as np
from PIL import Image
from ultralytics import YOLO

import config

logger = logging.getLogger("detector")


class BoarDetector:
    """野猪检测器，线程安全"""

    def __init__(self):
        self.model = None
        self.device = config.DEVICE
        self.input_size = config.INPUT_SIZE
        self.conf_threshold = config.CONFIDENCE_THRESHOLD
        self.iou_threshold = config.IOU_THRESHOLD
        self._lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        """加载模型并预热"""
        logger.info(f"正在加载模型: {config.MODEL_PATH}")
        t0 = time.time()

        self.model = YOLO(config.MODEL_PATH)

        # 确定设备
        if self.device is None:
            import torch
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logger.info(f"推理设备: {self.device}")

        # 预热：执行一次 dummy 推理
        dummy = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        self.model.predict(dummy, device=self.device, verbose=False)

        elapsed = time.time() - t0
        logger.info(f"模型加载完成，耗时 {elapsed:.2f}s")

    def _validate_and_decode(self, image_data: bytes) -> np.ndarray:
        """校验图片数据并解码为 numpy 数组"""
        # 校验文件头魔术数
        if image_data.startswith(b'\xff\xd8'):
            fmt = "JPEG"
        elif image_data.startswith(b'\x89PNG'):
            fmt = "PNG"
        elif image_data.startswith(b'BM'):
            fmt = "BMP"
        else:
            raise ValueError("不支持的图片格式，仅支持 JPEG/PNG/BMP")

        # 解码
        try:
            img = Image.open(BytesIO(image_data))
            img = img.convert("RGB")
        except Exception as e:
            raise ValueError(f"图片解码失败: {e}")

        # 校验尺寸
        if img.width != self.input_size or img.height != self.input_size:
            raise ValueError(
                f"图片尺寸必须是 {self.input_size}×{self.input_size}，"
                f"实际为 {img.width}×{img.height}"
            )

        return np.array(img)

    def detect(self, image_data: bytes) -> dict:
        """
        执行目标检测

        参数:
            image_data: 图片二进制数据（JPEG/PNG/BMP, 640×640）

        返回:
            {
                "detections": [
                    {
                        "class": "boar",
                        "class_id": 0,
                        "confidence": 0.934,
                        "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6}
                    }
                ],
                "image_width": 640,
                "image_height": 640,
                "inference_time_ms": 95.3
            }
        """
        # 1. 校验并解码图片
        img_array = self._validate_and_decode(image_data)
        img_height, img_width = img_array.shape[:2]

        # 2. 推理（加锁保证线程安全）
        t0 = time.time()
        with self._lock:
            results = self.model.predict(
                img_array,
                device=self.device,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )
        inference_ms = (time.time() - t0) * 1000

        # 3. 解析结果
        detections = []
        boxes = results[0].boxes
        if boxes is not None:
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                xyxyn = box.xyxyn[0].tolist()

                detections.append({
                    "class": self.model.names[cls_id],
                    "class_id": cls_id,
                    "confidence": round(conf, 4),
                    "bbox": {
                        "x1": round(xyxyn[0], 6),
                        "y1": round(xyxyn[1], 6),
                        "x2": round(xyxyn[2], 6),
                        "y2": round(xyxyn[3], 6),
                    }
                })

        return {
            "detections": detections,
            "image_width": img_width,
            "image_height": img_height,
            "inference_time_ms": round(inference_ms, 2),
        }
