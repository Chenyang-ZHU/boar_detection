"""模型加载与推理封装（图像/视频坐标返回 + 视频画框返回）"""

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


class ClientDisconnected(Exception):
    """客户端已断开连接，中止处理"""
    pass


class ProcessingTimeout(Exception):
    """单请求处理超时"""
    pass


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

    def _check_abort(self, is_closed, deadline):
        """检查是否需要中止处理：客户端断开或处理超时"""
        if is_closed and is_closed():
            raise ClientDisconnected()
        if deadline and time.time() > deadline:
            raise ProcessingTimeout("处理超时")

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

    def _parse_detections(self, result) -> list:
        """从推理结果解析检测列表（归一化 bbox，范围 0~1）"""
        detections = []
        boxes = result.boxes
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
        return detections

    # ------------------------------------------------------------------
    # 图像检测：返回检测坐标
    # ------------------------------------------------------------------
    def _validate_and_decode(self, image_data: bytes) -> np.ndarray:
        """校验图片格式，解码为 RGB numpy 数组（保持原始分辨率，尺寸不限）"""
        # 校验文件头魔术数
        if image_data.startswith(b'\xff\xd8'):
            fmt = "JPEG"
        elif image_data.startswith(b'\x89PNG'):
            fmt = "PNG"
        elif image_data.startswith(b'BM'):
            fmt = "BMP"
        else:
            raise ValueError("不支持的图片格式，仅支持 JPEG/PNG/BMP")

        # 解码（接受任意尺寸，尺寸限制由 detect_image_coords 统一处理）
        try:
            img = Image.open(BytesIO(image_data))
            img = img.convert("RGB")
        except Exception as e:
            raise ValueError(f"图片解码失败: {e}")

        return np.array(img)

    def detect_image_coords(self, image_data: bytes, is_closed=None, timeout=None) -> dict:
        """
        图像目标检测，返回检测坐标（归一化 bbox）。

        接受任意尺寸图片，按原尺寸处理；超过 IMAGE_HARD_LIMIT_SIDE 或
        文件过大时抛出 ValueError（含原始尺寸说明）；处理超时抛 ProcessingTimeout。

        参数:
            image_data: 图片二进制数据（JPEG/PNG/BMP，任意尺寸）
            is_closed: 可调用，返回 True 表示客户端已断开（可选）
            timeout: 处理超时秒数（可选）

        返回:
            {
                "detections": [{"class","class_id","confidence","bbox":{x1,y1,x2,y2}}],
                "image_width", "image_height", "inference_time_ms"
            }
            bbox 为归一化坐标（0~1）
        """
        # 0. 文件大小校验（超出上限返回说明）
        if len(image_data) > config.IMAGE_MAX_FILE_BYTES:
            raise ValueError(
                f"图片文件过大（{len(image_data) / 1024 / 1024:.1f}MB，原始数据大小），"
                f"超过处理上限 {config.IMAGE_MAX_FILE_BYTES / 1024 / 1024:.0f}MB"
            )

        # 1. 解码（RGB，保持原始分辨率）
        img_rgb = self._validate_and_decode(image_data)
        orig_h, orig_w = img_rgb.shape[:2]

        # 硬上限：长边过大则返回说明（含原始尺寸）
        if max(orig_w, orig_h) > config.IMAGE_HARD_LIMIT_SIDE:
            raise ValueError(
                f"图片过大（原始尺寸 {orig_w}×{orig_h}，原始数据大小 "
                f"{len(image_data) / 1024 / 1024:.1f}MB），长边超过 "
                f"{config.IMAGE_HARD_LIMIT_SIDE}px，请先压缩"
            )

        # 2. 推理（按原始分辨率），检查断开/超时
        deadline = time.time() + timeout if timeout else None
        self._check_abort(is_closed, deadline)
        t0 = time.time()
        result = self._infer(img_rgb)
        self._check_abort(is_closed, deadline)
        inference_ms = (time.time() - t0) * 1000

        # 3. 解析坐标
        detections = self._parse_detections(result)
        logger.info(
            f"图像检测完成: {len(detections)} 个目标, {orig_w}×{orig_h}, "
            f"耗时 {inference_ms:.1f}ms"
        )
        return {
            "detections": detections,
            "image_width": orig_w,
            "image_height": orig_h,
            "inference_time_ms": round(inference_ms, 2),
        }

    # ------------------------------------------------------------------
    # 视频检测：坐标 / 画框 mp4 两种
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

    def detect_video_coords(self, video_data: bytes, is_closed=None, timeout=None) -> dict:
        """
        视频逐帧目标检测，返回每帧检测坐标（归一化 bbox）。

        接受任意尺寸/时长视频，按原尺寸逐帧处理；文件超过 VIDEO_MAX_SIZE 或
        时长超过 VIDEO_MAX_DURATION 时抛出 ValueError（含原始信息）；
        客户端断开抛 ClientDisconnected，超时抛 ProcessingTimeout。

        参数:
            video_data: 视频二进制数据（mp4/avi/mov，任意尺寸）
            is_closed: 可调用，返回 True 表示客户端已断开（可选）
            timeout: 处理超时秒数（可选）

        返回:
            {
                "frame_width", "frame_height", "fps", "frame_count", "duration_sec",
                "frames": [{"index", "timestamp_ms", "detections":[...]}, ...]
            }
            无检测的帧 detections 为空数组；bbox 为归一化坐标（0~1）
        """
        # 0. 文件大小校验（超出上限返回说明，含原始大小）
        if len(video_data) > config.VIDEO_MAX_SIZE:
            raise ValueError(
                f"视频文件过大（{len(video_data) / 1024 / 1024:.1f}MB，原始数据大小），"
                f"超过处理上限 {config.VIDEO_MAX_SIZE / 1024 / 1024:.0f}MB"
            )

        tmp_in = None
        cap = None
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

            # 2. 校验时长（超出上限返回说明，含原始时长）
            duration = total_frames / fps if fps > 0 else 0
            if duration > config.VIDEO_MAX_DURATION:
                raise ValueError(
                    f"视频时长 {duration:.1f} 秒超过处理上限 "
                    f"{config.VIDEO_MAX_DURATION} 秒（原始时长 {duration:.1f}s，"
                    f"原始数据大小 {len(video_data) / 1024 / 1024:.1f}MB）"
                )
            if width <= 0 or height <= 0:
                raise ValueError("视频尺寸无效")

            # 3. 逐帧检测（每帧检查断开/超时）
            deadline = time.time() + timeout if timeout else None
            frames = []
            index = 0
            t0 = time.time()
            while True:
                self._check_abort(is_closed, deadline)
                ret, frame = cap.read()
                if not ret:
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self._infer(frame_rgb)
                detections = self._parse_detections(result)

                frames.append({
                    "index": index,
                    "timestamp_ms": round(index * 1000.0 / fps, 2) if fps > 0 else 0,
                    "detections": detections,
                })
                index += 1

            inference_ms = (time.time() - t0) * 1000
            logger.info(
                f"视频坐标检测完成: {index} 帧, 耗时 {inference_ms / 1000:.1f}s"
            )

            return {
                "frame_width": width,
                "frame_height": height,
                "fps": round(fps, 2),
                "frame_count": index,
                "duration_sec": round(duration, 2),
                "frames": frames,
            }
        finally:
            if cap is not None:
                cap.release()
            if tmp_in and os.path.exists(tmp_in):
                try:
                    os.remove(tmp_in)
                except OSError:
                    pass

    def detect_video(self, video_data: bytes, is_closed=None, timeout=None) -> tuple:
        """
        视频逐帧目标检测，返回画了 bbox 的 mp4 视频字节和原始信息。

        接受任意尺寸/时长视频，按原尺寸处理；文件超过 VIDEO_MAX_SIZE 或
        时长超过 VIDEO_MAX_DURATION 时抛出 ValueError（含原始信息）；
        客户端断开抛 ClientDisconnected，超时抛 ProcessingTimeout。

        参数:
            video_data: 视频二进制数据（mp4/avi/mov，任意尺寸）
            is_closed: 可调用，返回 True 表示客户端已断开（可选）
            timeout: 处理超时秒数（可选）

        返回:
            (画框 mp4 视频字节, meta字典)，meta 含 original_width/original_height/
            original_duration/original_size/processed_width/processed_height
        """
        # 0. 文件大小校验（超出上限返回说明，含原始大小）
        if len(video_data) > config.VIDEO_MAX_SIZE:
            raise ValueError(
                f"视频文件过大（{len(video_data) / 1024 / 1024:.1f}MB，原始数据大小），"
                f"超过处理上限 {config.VIDEO_MAX_SIZE / 1024 / 1024:.0f}MB"
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

            # 2. 校验时长（超出上限返回说明，含原始时长）
            duration = total_frames / fps if fps > 0 else 0
            if duration > config.VIDEO_MAX_DURATION:
                raise ValueError(
                    f"视频时长 {duration:.1f} 秒超过处理上限 "
                    f"{config.VIDEO_MAX_DURATION} 秒（原始时长 {duration:.1f}s，"
                    f"原始数据大小 {len(video_data) / 1024 / 1024:.1f}MB）"
                )
            if width <= 0 or height <= 0:
                raise ValueError("视频尺寸无效")

            # 3. 按原始帧分辨率处理（不缩放，输出与原始视频同尺寸）
            out_width, out_height = width, height

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

            # 5. 逐帧检测（每帧检查断开/超时）
            deadline = time.time() + timeout if timeout else None
            t0 = time.time()
            frame_count = 0
            while True:
                self._check_abort(is_closed, deadline)
                ret, frame = cap.read()
                if not ret:
                    break

                # BGR → RGB 推理（保持原始帧分辨率）
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
                video_bytes = f.read()

            meta = {
                "original_width": width,
                "original_height": height,
                "original_duration": round(duration, 2),
                "original_size": len(video_data),
                "processed_width": out_width,
                "processed_height": out_height,
            }
            return video_bytes, meta

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
