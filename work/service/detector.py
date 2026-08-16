"""模型加载与推理封装（支持图像/视频画框返回）"""

import os
import time
import logging
import tempfile
import threading
from io import BytesIO

import numpy as np
import cv2
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

    # ------------------------------------------------------------------
    # 模型加载
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 推理核心
    # ------------------------------------------------------------------
    def _infer(self, img_array: np.ndarray):
        """执行推理（加锁保证线程安全）"""
        with self._lock:
            results = self.model.predict(
                img_array,
                device=self.device,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )
        return results[0]

    def _draw_boxes(self, frame_bgr: np.ndarray, result) -> np.ndarray:
        """在 BGR 帧上绘制检测框"""
        boxes = result.boxes
        if boxes is None:
            return frame_bgr

        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

            label = f"{self.model.names[cls_id]} {conf:.2f}"

            # 绘制矩形框
            cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 绘制标签背景 + 文字
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_y = y1 - 4 if y1 - 4 > th else y1 + th + 4
            cv2.rectangle(frame_bgr, (x1, label_y - th - 4), (x1 + tw, label_y), (0, 255, 0), -1)
            cv2.putText(frame_bgr, label, (x1, label_y - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        return frame_bgr

    # ------------------------------------------------------------------
    # 图像检测：返回画框 JPEG
    # ------------------------------------------------------------------
    def _validate_and_decode(self, image_data: bytes) -> np.ndarray:
        """校验图片格式和尺寸，解码为 RGB numpy 数组（保持原始分辨率）"""
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

        # 校验尺寸：长边不得超过限制
        max_side = max(img.width, img.height)
        if max_side > config.MAX_IMAGE_SIZE:
            raise ValueError(
                f"图片尺寸过大（{img.width}×{img.height}），"
                f"长边不能超过 {config.MAX_IMAGE_SIZE}px"
            )

        return np.array(img)

    def detect_image(self, image_data: bytes) -> bytes:
        """
        图像目标检测，返回画了 bbox 的 JPEG 图片字节

        参数:
            image_data: 图片二进制数据（JPEG/PNG/BMP, 长边 ≤ 1080px）

        返回:
            画框 JPEG 图片字节（未检测到目标时返回原图）
        """
        # 1. 解码（RGB）
        img_rgb = self._validate_and_decode(image_data)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

        # 2. 推理
        t0 = time.time()
        result = self._infer(img_rgb)
        inference_ms = (time.time() - t0) * 1000

        # 3. 画框
        img_bgr = self._draw_boxes(img_bgr, result)

        # 4. 编码为 JPEG
        ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError("图片编码失败")

        det_count = 0 if result.boxes is None else len(result.boxes)
        logger.info(f"图像检测完成: {det_count} 个目标, 耗时 {inference_ms:.1f}ms")
        return buf.tobytes()

    # ------------------------------------------------------------------
    # 视频检测：逐帧返回画框 mp4
    # ------------------------------------------------------------------
    def _pick_video_codec(self, fourcc_try_list, filename, fps, size):
        """根据策略选择可用编码器"""
        if config.VIDEO_CODEC == "mp4v":
            return cv2.VideoWriter_fourcc(*"mp4v")
        if config.VIDEO_CODEC == "avc1":
            return cv2.VideoWriter_fourcc(*"avc1")

        # auto：尝试 H.264，失败回退 mp4v
        for codec in fourcc_try_list:
            writer = cv2.VideoWriter(filename, codec, fps, size)
            if writer.isOpened():
                writer.release()
                return codec
        # 兜底
        return cv2.VideoWriter_fourcc(*"mp4v")

    def detect_video(self, video_data: bytes) -> bytes:
        """
        视频逐帧目标检测，返回画了 bbox 的 mp4 视频字节

        参数:
            video_data: 视频二进制数据（mp4/avi/mov）

        返回:
            逐帧画框 mp4 视频字节

        限制:
            - 大小 ≤ config.MAX_VIDEO_SIZE
            - 时长 ≤ config.MAX_VIDEO_DURATION 秒
            - 长边 > config.MAX_VIDEO_SIDE 自动缩放
        """
        # 大小校验
        if len(video_data) > config.MAX_VIDEO_SIZE:
            raise ValueError(
                f"视频过大（{len(video_data) / 1024 / 1024:.1f}MB），"
                f"不能超过 {config.MAX_VIDEO_SIZE / 1024 / 1024:.0f}MB"
            )

        tmp_in = None
        tmp_out = None
        cap = None
        writer = None
        try:
            # 1. 写入临时文件并打开
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                f.write(video_data)
                tmp_in = f.name

            cap = cv2.VideoCapture(tmp_in)
            if not cap.isOpened():
                raise ValueError("无法读取视频，请确认视频格式为 mp4/avi/mov")

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 2. 校验时长
            duration = total_frames / fps if fps > 0 else 0
            if duration > config.MAX_VIDEO_DURATION:
                raise ValueError(
                    f"视频时长 {duration:.1f} 秒超过限制 "
                    f"{config.MAX_VIDEO_DURATION} 秒"
                )
            if width <= 0 or height <= 0:
                raise ValueError("视频尺寸无效")

            # 3. 计算输出尺寸（长边超过限制则缩放）
            out_width, out_height = width, height
            max_side = max(width, height)
            if max_side > config.MAX_VIDEO_SIDE:
                scale = config.MAX_VIDEO_SIDE / max_side
                out_width = int(width * scale)
                out_height = int(height * scale)

            logger.info(
                f"视频处理: {width}×{height}, {fps:.0f}fps, "
                f"{duration:.1f}s, {total_frames} 帧 → 输出 {out_width}×{out_height}"
            )

            # 4. 创建输出写入器
            tmp_out = os.path.join(
                tempfile.gettempdir(),
                f"boar_detect_{int(time.time())}.mp4"
            )
            codec = self._pick_video_codec(
                [cv2.VideoWriter_fourcc(*"avc1"), cv2.VideoWriter_fourcc(*"mp4v")],
                tmp_out, fps, (out_width, out_height)
            )
            writer = cv2.VideoWriter(
                tmp_out, codec, fps, (out_width, out_height)
            )
            if not writer.isOpened():
                raise ValueError("视频编码器初始化失败")

            # 5. 逐帧检测
            t0 = time.time()
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 缩放（如需）
                if out_width != width or out_height != height:
                    frame = cv2.resize(frame, (out_width, out_height))

                # BGR → RGB 推理
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self._infer(frame_rgb)

                # 画框（BGR）
                frame = self._draw_boxes(frame, result)
                writer.write(frame)
                frame_count += 1

            inference_ms = (time.time() - t0) * 1000
            logger.info(
                f"视频检测完成: {frame_count} 帧, 耗时 {inference_ms / 1000:.1f}s"
            )

            # 6. 释放并读取结果
            writer.release()
            writer = None
            cap.release()
            cap = None

            with open(tmp_out, "rb") as f:
                return f.read()

        finally:
            if writer is not None:
                writer.release()
            if cap is not None:
                cap.release()
            # 清理临时文件
            for path in (tmp_in, tmp_out):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
