"""
野猪检测核心 - ONNX Runtime 推理引擎
Wild Boar Detector - ONNX Runtime Inference Engine

支持: 图片检测 / 视频检测 / 批量处理
"""

import os
import sys
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional


class BoarDetector:
    """野猪检测器 - 使用 ONNX 模型"""

    def __init__(self, model_path: str, conf_threshold: float = 0.25, iou_threshold: float = 0.45):
        """
        初始化检测器
        
        Args:
            model_path: ONNX 模型路径
            conf_threshold: 置信度阈值 (默认 0.25)
            iou_threshold: NMS 的 IoU 阈值 (默认 0.45)
        """
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("需要安装 onnxruntime: pip install onnxruntime")

        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_width = 640
        self.input_height = 640

        # 加载模型
        if not Path(model_path).exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        # 优先使用 GPU (CUDA/ DirectML)
        providers = []
        available = ort.get_available_providers()
        for p in ['CUDAExecutionProvider', 'DmlExecutionProvider', 'CPUExecutionProvider']:
            if p in available:
                providers.append(p)
        
        self.session = ort.InferenceSession(model_path, providers=providers)
        
        # 获取输入输出信息
        self.input_name = self.session.get_inputs()[0].name
        input_shape = self.session.get_inputs()[0].shape
        self.input_height, self.input_width = input_shape[2], input_shape[3] if len(input_shape) == 4 else (640, 640)

        provider_name = self.session.get_providers()[0]
        print(f"✅ 模型加载成功: {Path(model_path).name}")
        print(f"   推理设备: {provider_name}")
        print(f"   输入尺寸: {self.input_width}x{self.input_height}")

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """预处理图片为模型输入格式"""
        orig_h, orig_w = image.shape[:2]
        scale = min(self.input_width / orig_w, self.input_height / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # 填充到正方形
        dw = self.input_width - new_w
        dh = self.input_height - new_h
        top, bottom = dh // 2, dh - dh // 2
        left, right = dw // 2, dw - dw // 2
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, 
                                     cv2.BORDER_CONSTANT, value=(114, 114, 114))

        # 归一化 + 转换格式
        blob = padded.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)

        return blob, scale, (left, top)

    def postprocess(self, outputs: np.ndarray, scale: float, padding: Tuple[int, int], 
                    orig_shape: Tuple[int, int]) -> List[dict]:
        """后处理模型输出为检测结果"""
        orig_h, orig_w = orig_shape
        predictions = np.squeeze(outputs).T  # (num_detections, 6)

        # 过滤低置信度
        mask = predictions[:, 4] > self.conf_threshold
        predictions = predictions[mask]

        if len(predictions) == 0:
            return []

        boxes = []
        scores = []
        
        left, top = padding
        for pred in predictions:
            xc, yc, w, h = pred[:4]
            conf = pred[4]
            
            # 从填充后的坐标映射回原始图片
            x1 = (xc - w / 2 - left) / scale
            y1 = (yc - h / 2 - top) / scale
            x2 = (xc + w / 2 - left) / scale
            y2 = (yc + h / 2 - top) / scale

            # 裁剪到图片范围内
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))

            boxes.append([x1, y1, x2, y2])
            scores.append(conf)

        # NMS (非极大值抑制)
        indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.iou_threshold)
        
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                results.append({
                    'box': boxes[i],
                    'confidence': float(scores[i]),
                    'class_id': 0,
                    'class_name': '野猪 boar'
                })

        return results

    def detect_image(self, image: np.ndarray) -> List[dict]:
        """检测单张图片"""
        blob, scale, padding = self.preprocess(image)
        outputs = self.session.run(None, {self.input_name: blob})[0]
        return self.postprocess(outputs, scale, padding, image.shape[:2])

    def detect_file(self, filepath: str) -> Tuple[List[dict], Optional[np.ndarray]]:
        """检测图片文件，返回检测结果和标注后的图片"""
        image = cv2.imread(filepath)
        if image is None:
            return [], None
        
        results = self.detect_image(image)
        annotated = self.draw_results(image, results)
        return results, annotated

    def detect_video_frame(self, frame: np.ndarray) -> List[dict]:
        """检测单帧视频"""
        return self.detect_image(frame)

    @staticmethod
    def draw_results(image: np.ndarray, results: List[dict], show_label: bool = True) -> np.ndarray:
        """在图片上绘制检测结果"""
        annotated = image.copy()
        
        for det in results:
            x1, y1, x2, y2 = [int(v) for v in det['box']]
            conf = det['confidence']
            label = f"{det['class_name']} {conf:.2f}"

            # 绘制框 (绿色)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
            
            if show_label:
                # 绘制标签背景
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 8, y1), (0, 200, 0), -1)
                # 绘制标签文字
                cv2.putText(annotated, label, (x1 + 4, y1 - 6),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return annotated

    def process_video(self, video_path: str, output_path: str = None, 
                      frame_skip: int = 0, show_progress: callable = None) -> dict:
        """
        处理视频文件
        
        Args:
            video_path: 视频文件路径
            output_path: 输出视频路径 (None 则不保存)
            frame_skip: 跳帧数 (0=处理所有帧)
            show_progress: 进度回调函数 func(current, total)
            
        Returns:
            统计信息 dict
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        out = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

        stats = {
            'total_frames': total_frames,
            'processed_frames': 0,
            'boar_frames': 0,
            'total_boars': 0,
            'fps': fps,
            'duration_sec': total_frames / fps if fps > 0 else 0,
        }

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_skip > 0 and (frame_idx - 1) % (frame_skip + 1) != 0:
                continue

            results = self.detect_video_frame(frame)
            stats['processed_frames'] += 1
            
            if len(results) > 0:
                stats['boar_frames'] += 1
                stats['total_boars'] += len(results)
                annotated = self.draw_results(frame, results)
            else:
                annotated = frame

            if out:
                out.write(annotated)

            if show_progress:
                show_progress(frame_idx, total_frames)

        cap.release()
        if out:
            out.release()

        return stats

    def process_folder(self, folder_path: str, output_dir: str = None, 
                       extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp')) -> List[dict]:
        """
        批量处理文件夹中的图片
        
        Returns:
            每个文件的检测结果列表
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")

        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        all_results = []
        image_files = []
        for ext in extensions:
            image_files.extend(folder.glob(f'*{ext}'))
            image_files.extend(folder.glob(f'*{ext.upper()}'))

        image_files.sort()
        total = len(image_files)

        for idx, img_path in enumerate(image_files):
            results, annotated = self.detect_file(str(img_path))
            
            result_info = {
                'file': str(img_path),
                'filename': img_path.name,
                'detections': len(results),
                'results': results,
                'index': idx + 1,
                'total': total,
            }
            
            if output_dir and annotated is not None:
                out_path = Path(output_dir) / img_path.name
                cv2.imwrite(str(out_path), annotated)
                result_info['output'] = str(out_path)

            all_results.append(result_info)

        return all_results
