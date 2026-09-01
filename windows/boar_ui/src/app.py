#!/usr/bin/env python3
"""
野猪检测桌面工具 - Wild Boar Detector Desktop App
可直接在 Windows 11 上运行，支持图片和视频检测
"""

import os
import sys
import cv2
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from tkinter import (
    Tk, Toplevel, Frame, Label, Button, Text, Entry,
    filedialog, messagebox, ttk, Canvas, Scrollbar, scrolledtext
)
from tkinter.ttk import Progressbar

# 确保能找到 detector 模块
sys.path.insert(0, str(Path(__file__).parent))
from detector import BoarDetector


# ─── 工具函数 ──────────────────────────────────────────────────────────────


def resource_path(relative_path):
    """获取资源文件路径（兼容 PyInstaller 打包）"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(base_path)  # src/ -> boar_deploy/
    return os.path.join(base_path, relative_path)


def find_model():
    """查找模型文件"""
    search_paths = [
        resource_path("model/best.onnx"),
        resource_path("model/best.pt"),
        "model/best.onnx",
        "model/best.pt",
        "../model/best.onnx",
        "../model/best.pt",
    ]
    for p in search_paths:
        if Path(p).exists():
            return str(Path(p).resolve())
    return None


def format_time(seconds):
    """格式化时间显示"""
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    elif seconds < 3600:
        return f"{seconds // 60} 分 {seconds % 60:.0f} 秒"
    else:
        return f"{seconds // 3600} 时 {(seconds % 3600) // 60} 分"


def list_images(folder, extensions=('.jpg', '.jpeg', '.png', '.bmp')):
    """列出文件夹中所有图片"""
    images = []
    for ext in extensions:
        images.extend(Path(folder).glob(f'*{ext}'))
        images.extend(Path(folder).glob(f'*{ext.upper()}'))
    return sorted(images)


def list_videos(folder, extensions=('.mp4', '.avi', '.mov', '.mkv', '.wmv')):
    """列出文件夹中所有视频"""
    videos = []
    for ext in extensions:
        videos.extend(Path(folder).glob(f'*{ext}'))
        videos.extend(Path(folder).glob(f'*{ext.upper()}'))
    return sorted(videos)


# ─── 主应用 ────────────────────────────────────────────────────────────────


class BoarDetectorApp:
    """野猪检测桌面应用"""

    def __init__(self, root):
        self.root = root
        self.root.title("🐗 野猪检测工具 v1.0")
        self.root.geometry("900x680")
        self.root.minsize(800, 600)

        # 检测器
        self.detector = None
        self.model_path = find_model()
        self.loading = False
        self.processing = False

        # 构建界面
        self._build_ui()

        # 自动加载模型
        if self.model_path:
            self.root.after(100, self._auto_load_model)
        else:
            self.log("⚠️ 未找到模型文件 (best.onnx / best.pt)")
            self.log("   请将模型文件放入 model/ 目录")

    def _build_ui(self):
        """构建界面"""
        # ── 顶部标题 ──
        title_frame = Frame(self.root, bg="#2d5a27", height=60)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        Label(title_frame, text="🐗 野猪检测工具", fg="white", bg="#2d5a27",
              font=("Microsoft YaHei", 18, "bold")).pack(side="left", padx=20, pady=12)
        self.status_label = Label(title_frame, text="就绪", fg="#ccc", bg="#2d5a27",
                                   font=("Microsoft YaHei", 11))
        self.status_label.pack(side="right", padx=20)

        # ── 主内容 ──
        main_frame = Frame(self.root, bg="#f0f0f0")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 左侧：操作面板
        left = Frame(main_frame, bg="white", relief="groove", bd=1)
        left.pack(side="left", fill="y", padx=(0, 10), pady=0)
        left.pack_propagate(False)
        left.configure(width=280)

        # 模型信息
        model_frame = Frame(left, bg="white")
        model_frame.pack(fill="x", padx=12, pady=(12, 5))
        Label(model_frame, text="📦 模型状态", font=("Microsoft YaHei", 12, "bold"),
              bg="white").pack(anchor="w")
        
        self.model_info = Text(model_frame, height=3, width=32, font=("Consolas", 9),
                                bg="#f8f8f8", relief="flat", state="disabled")
        self.model_info.pack(fill="x", pady=4)
        self._update_model_info("未加载")

        # 参数设置
        param_frame = Frame(left, bg="white")
        param_frame.pack(fill="x", padx=12, pady=5)

        Label(param_frame, text="⚙️ 检测参数", font=("Microsoft YaHei", 12, "bold"),
              bg="white").pack(anchor="w")

        # 置信度阈值
        conf_frame = Frame(param_frame, bg="white")
        conf_frame.pack(fill="x", pady=2)
        Label(conf_frame, text="置信度阈值:", bg="white", width=12, anchor="w").pack(side="left")
        self.conf_var = StringVar(value="0.25")
        Entry(conf_frame, textvariable=self.conf_var, width=8, font=("Consolas", 10)).pack(side="left")

        # IoU阈值
        iou_frame = Frame(param_frame, bg="white")
        iou_frame.pack(fill="x", pady=2)
        Label(iou_frame, text="IoU 阈值:", bg="white", width=12, anchor="w").pack(side="left")
        self.iou_var = StringVar(value="0.45")
        Entry(iou_frame, textvariable=self.iou_var, width=8, font=("Consolas", 10)).pack(side="left")

        # 操作按钮
        btn_frame = Frame(left, bg="white")
        btn_frame.pack(fill="x", padx=12, pady=(10, 5))

        self.btn_image = Button(btn_frame, text="📷 检测单张图片", command=self.detect_single_image,
                                 bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10),
                                 padx=10, pady=6, state="disabled", cursor="hand2")
        self.btn_image.pack(fill="x", pady=3)

        self.btn_folder = Button(btn_frame, text="📁 批量检测图片", command=self.detect_folder,
                                  bg="#2196F3", fg="white", font=("Microsoft YaHei", 10),
                                  padx=10, pady=6, state="disabled", cursor="hand2")
        self.btn_folder.pack(fill="x", pady=3)

        self.btn_video = Button(btn_frame, text="🎬 检测视频", command=self.detect_video,
                                 bg="#FF9800", fg="white", font=("Microsoft YaHei", 10),
                                 padx=10, pady=6, state="disabled", cursor="hand2")
        self.btn_video.pack(fill="x", pady=3)

        self.btn_reload = Button(btn_frame, text="🔄 重新加载模型", command=self.reload_model,
                                  bg="#607D8B", fg="white", font=("Microsoft YaHei", 10),
                                  padx=10, pady=6, cursor="hand2")
        self.btn_reload.pack(fill="x", pady=(10, 3))

        # 进度条
        self.progress = Progressbar(left, orient="horizontal", length=250, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=(5, 0))

        self.progress_label = Label(left, text="", bg="white", font=("Microsoft YaHei", 9))
        self.progress_label.pack(padx=12, pady=2)

        # ── 右侧：日志/结果 ──
        right = Frame(main_frame, bg="white", relief="groove", bd=1)
        right.pack(side="right", fill="both", expand=True)

        # 标签页
        note = ttk.Notebook(right)
        note.pack(fill="both", expand=True, padx=5, pady=5)

        # 日志页
        log_tab = Frame(note, bg="white")
        note.add(log_tab, text="📋 运行日志")
        
        self.log_area = scrolledtext.ScrolledText(
            log_tab, wrap="word", font=("Consolas", 10),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            state="disabled", height=20
        )
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

        # 结果页
        result_tab = Frame(note, bg="white")
        note.add(result_tab, text="📊 检测结果")
        
        self.result_text = scrolledtext.ScrolledText(
            result_tab, wrap="word", font=("Consolas", 10),
            state="disabled", height=20
        )
        self.result_text.pack(fill="both", expand=True, padx=5, pady=5)

        # ── 底部状态栏 ──
        bottom = Frame(self.root, bg="#e0e0e0", height=28)
        bottom.pack(fill="x")
        bottom.pack_propagate(False)
        self.footer_label = Label(bottom, text="🐗 野猪检测工具 | 右键选择图片或视频", 
                                   bg="#e0e0e0", font=("Microsoft YaHei", 9))
        self.footer_label.pack(side="left", padx=12)

        self.log("🐗 野猪检测工具已启动")
        self.log(f"   模型路径: {self.model_path or '未找到'}")

    def _update_model_info(self, text):
        """更新模型信息框"""
        self.model_info.config(state="normal")
        self.model_info.delete(1.0, "end")
        self.model_info.insert(1.0, text)
        self.model_info.config(state="disabled")

    def _auto_load_model(self):
        """自动加载模型"""
        self.load_model(self.model_path)

    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state="normal")
        self.log_area.insert("end", f"[{timestamp}] {message}\n")
        self.log_area.see("end")
        self.log_area.config(state="disabled")

    def log_result(self, message):
        """添加结果"""
        self.result_text.config(state="normal")
        self.result_text.insert("end", message + "\n")
        self.result_text.see("end")
        self.result_text.config(state="disabled")

    def set_busy(self, busy=True):
        """设置忙碌状态"""
        state = "disabled" if busy else "normal"
        self.btn_image.config(state=state if self.detector else "disabled")
        self.btn_folder.config(state=state if self.detector else "disabled")
        self.btn_video.config(state=state if self.detector else "disabled")
        self.status_label.config(text="处理中..." if busy else "就绪")
        self.root.update()

    def load_model(self, model_path):
        """加载模型"""
        if self.loading or self.processing:
            return

        self.loading = True
        self.status_label.config(text="加载模型中...")

        def _load():
            try:
                conf = float(self.conf_var.get())
                iou = float(self.iou_var.get())
            except ValueError:
                conf, iou = 0.25, 0.45

            try:
                ext = Path(model_path).suffix.lower()
                if ext == '.onnx':
                    self.detector = BoarDetector(model_path, conf, iou)
                    self._update_model_info(
                        f"✅ 已加载\n   {Path(model_path).name}\n   置信度: {conf} | IoU: {iou}"
                    )
                elif ext == '.pt':
                    # 使用 ultralytics 加载
                    from ultralytics import YOLO
                    self.detector = _UltralyticsWrapper(model_path, conf, iou)
                    self._update_model_info(
                        f"✅ 已加载 (ultralytics)\n   {Path(model_path).name}\n   置信度: {conf} | IoU: {iou}"
                    )
                else:
                    self.log(f"❌ 不支持的模型格式: {ext}")
                    self._update_model_info("❌ 加载失败")
                    return

                self.log(f"✅ 模型加载成功: {Path(model_path).name}")
                self.root.after(0, lambda: self.btn_image.config(state="normal"))
                self.root.after(0, lambda: self.btn_folder.config(state="normal"))
                self.root.after(0, lambda: self.btn_video.config(state="normal"))

            except Exception as e:
                self.log(f"❌ 模型加载失败: {e}")
                self._update_model_info(f"❌ 加载失败\n   {str(e)[:50]}")
            finally:
                self.loading = False
                self.root.after(0, lambda: self.status_label.config(text="就绪"))

        threading.Thread(target=_load, daemon=True).start()

    def reload_model(self):
        """重新加载模型"""
        self.load_model(self.model_path)

    def detect_single_image(self):
        """检测单张图片"""
        if self.processing or not self.detector:
            return

        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        self.processing = True
        self.set_busy(True)
        self.log(f"📷 检测图片: {Path(file_path).name}")

        def _detect():
            try:
                update_params()
                results, annotated = self.detector.detect_file(file_path)
                
                self.log(f"   检测到 {len(results)} 头野猪")
                for r in results:
                    box = r['box']
                    self.log(f"   置信度 {r['confidence']:.2f} | 位置 ({int(box[0])},{int(box[1])}) -> ({int(box[2])},{int(box[3])})")

                if annotated is not None:
                    # 保存结果
                    out_dir = Path(file_path).parent / "boar_results"
                    out_dir.mkdir(exist_ok=True)
                    out_path = out_dir / f"boar_{Path(file_path).name}"
                    cv2.imwrite(str(out_path), annotated)
                    self.log(f"   结果已保存: {out_path}")
                    
                    # 显示结果信息
                    self.log_result(f"📷 {Path(file_path).name}")
                    self.log_result(f"   野猪数量: {len(results)} 头")
                    for i, r in enumerate(results, 1):
                        self.log_result(f"   #{i} 置信度: {r['confidence']:.2%}")
                    self.log_result(f"   结果图片: {out_path}")
                    self.log_result("")

                # 弹出提示
                self.root.after(0, lambda: messagebox.showinfo(
                    "检测完成", f"图片: {Path(file_path).name}\n野猪: {len(results)} 头\n结果保存在: boar_results/"
                ))

            except Exception as e:
                self.log(f"❌ 检测失败: {e}")
            finally:
                self.processing = False
                self.root.after(0, lambda: self.set_busy(False))

        def update_params():
            try:
                self.detector.conf_threshold = float(self.conf_var.get())
                self.detector.iou_threshold = float(self.iou_var.get())
            except ValueError:
                pass

        threading.Thread(target=_detect, daemon=True).start()

    def detect_folder(self):
        """批量检测图片文件夹"""
        if self.processing or not self.detector:
            return

        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
        if not folder:
            return

        self.processing = True
        self.set_busy(True)
        self.log(f"📁 批量检测: {folder}")

        def _detect():
            try:
                conf = float(self.conf_var.get())
                iou = float(self.iou_var.get())
                self.detector.conf_threshold = conf
                self.detector.iou_threshold = iou

                image_files = list_images(folder)
                total = len(image_files)
                self.log(f"   找到 {total} 张图片")

                if total == 0:
                    self.log("   没有找到图片文件")
                    self.root.after(0, lambda: messagebox.showinfo("提示", "所选文件夹中没有图片"))
                    return

                out_dir = Path(folder) / "boar_results"
                out_dir.mkdir(exist_ok=True)

                start_time = time.time()
                total_boars = 0

                for idx, img_path in enumerate(image_files):
                    results, annotated = self.detector.detect_file(str(img_path))
                    total_boars += len(results)

                    if annotated is not None:
                        out_path = out_dir / img_path.name
                        cv2.imwrite(str(out_path), annotated)

                    # 更新进度
                    progress = int((idx + 1) / total * 100)
                    self.root.after(0, lambda p=progress, i=idx+1, t=total: (
                        self.progress.configure(value=p),
                        self.progress_label.configure(text=f"{i}/{t} ({p}%)")
                    ))

                elapsed = time.time() - start_time
                self.log(f"✅ 批量检测完成!")
                self.log(f"   共 {total} 张图片, 检测到 {total_boars} 头野猪")
                self.log(f"   耗时: {format_time(elapsed)}")
                self.log(f"   结果保存在: {out_dir}")

                self.log_result(f"📁 批量检测结果: {Path(folder).name}")
                self.log_result(f"   图片总数: {total} 张")
                self.log_result(f"   野猪总数: {total_boars} 头")
                self.log_result(f"   耗时: {format_time(elapsed)}")
                self.log_result(f"   平均: {elapsed/total:.1f} 秒/张" if total > 0 else "")
                self.log_result(f"   结果目录: {out_dir}")
                self.log_result("")

                self.root.after(0, lambda: messagebox.showinfo(
                    "批量检测完成",
                    f"处理了 {total} 张图片\n检测到 {total_boars} 头野猪\n耗时 {format_time(elapsed)}"
                ))

            except Exception as e:
                self.log(f"❌ 批量检测失败: {e}")
            finally:
                self.processing = False
                self.progress.configure(value=0)
                self.progress_label.configure(text="")
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=_detect, daemon=True).start()

    def detect_video(self):
        """检测视频文件"""
        if self.processing or not self.detector:
            return

        file_path = filedialog.askopenfilename(
            title="选择视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        self.processing = True
        self.set_busy(True)
        self.log(f"🎬 检测视频: {Path(file_path).name}")

        def _detect():
            try:
                conf = float(self.conf_var.get())
                iou = float(self.iou_var.get())
                self.detector.conf_threshold = conf
                self.detector.iou_threshold = iou

                out_dir = Path(file_path).parent / "boar_results"
                out_dir.mkdir(exist_ok=True)
                out_path = str(out_dir / f"boar_{Path(file_path).name}")

                self.log(f"   输出: {out_path}")

                def progress_cb(current, total):
                    pct = int(current / total * 100)
                    self.root.after(0, lambda: (
                        self.progress.configure(value=pct),
                        self.progress_label.configure(text=f"帧 {current}/{total} ({pct}%)")
                    ))

                start_time = time.time()
                stats = self.detector.process_video(
                    file_path, 
                    output_path=out_path,
                    frame_skip=0,
                    show_progress=progress_cb
                )
                elapsed = time.time() - start_time

                self.log(f"✅ 视频检测完成!")
                self.log(f"   视频时长: {format_time(stats['duration_sec'])}")
                self.log(f"   总帧数: {stats['total_frames']}")
                self.log(f"   含野猪帧: {stats['boar_frames']} 帧")
                self.log(f"   野猪出现总次数: {stats['total_boars']} 次")
                self.log(f"   处理耗时: {format_time(elapsed)}")
                self.log(f"   结果视频: {out_path}")

                self.log_result(f"🎬 视频检测结果: {Path(file_path).name}")
                self.log_result(f"   视频时长: {stats['duration_sec']:.1f} 秒")
                self.log_result(f"   含野猪帧: {stats['boar_frames']}/{stats['processed_frames']} 帧")
                self.log_result(f"   野猪出现次数: {stats['total_boars']} 次")
                self.log_result(f"   处理耗时: {format_time(elapsed)}")
                self.log_result(f"   结果视频: {out_path}")
                self.log_result("")

                self.root.after(0, lambda: messagebox.showinfo(
                    "视频检测完成",
                    f"视频: {Path(file_path).name}\n"
                    f"野猪出现: {stats['boar_frames']} 帧\n"
                    f"处理耗时: {format_time(elapsed)}\n"
                    f"结果保存在: boar_results/"
                ))

            except Exception as e:
                self.log(f"❌ 视频检测失败: {e}")
            finally:
                self.processing = False
                self.progress.configure(value=0)
                self.progress_label.configure(text="")
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=_detect, daemon=True).start()


# ─── Ultralytics Wrapper (支持 .pt 模型) ───────────────────────────────────


class _UltralyticsWrapper:
    """包装 ultralytics YOLO 模型，兼容 BoarDetector 接口"""

    def __init__(self, model_path, conf=0.25, iou=0.45):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.conf_threshold = conf
        self.iou_threshold = iou
        self.input_width = 640
        self.input_height = 640
        provider = "CPU"
        try:
            import torch
            if torch.cuda.is_available():
                provider = "CUDA"
        except:
            pass
        print(f"✅ Ultralytics 模型加载: {Path(model_path).name} ({provider})")

    def detect_file(self, filepath):
        results = self.model.predict(
            source=filepath,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=640,
            verbose=False
        )[0]
        return self._parse_results(results), results.plot() if hasattr(results, 'plot') else None

    def detect_image(self, image):
        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=640,
            verbose=False
        )[0]
        return self._parse_results(results)

    def detect_video_frame(self, frame):
        return self.detect_image(frame)

    def process_video(self, video_path, output_path=None, frame_skip=0, show_progress=None):
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        out = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

        stats = {
            'total_frames': total_frames, 'processed_frames': 0,
            'boar_frames': 0, 'total_boars': 0,
            'fps': fps, 'duration_sec': total_frames / fps if fps > 0 else 0,
        }

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_skip > 0 and (frame_idx - 1) % (frame_skip + 1) != 0:
                continue

            results = self.model.predict(source=frame, conf=self.conf_threshold,
                                          iou=self.iou_threshold, imgsz=640, verbose=False)[0]
            stats['processed_frames'] += 1
            if len(results.boxes) > 0:
                stats['boar_frames'] += 1
                stats['total_boars'] += len(results.boxes)

            annotated = results.plot() if hasattr(results, 'plot') else frame
            if out:
                out.write(annotated)
            if show_progress:
                show_progress(frame_idx, total_frames)

        cap.release()
        if out:
            out.release()
        return stats

    def _parse_results(self, results):
        detections = []
        if results.boxes is not None:
            for box in results.boxes:
                x1, y1, x2, y2 = box.xyxyn[0].tolist()
                detections.append({
                    'box': [x1, y1, x2, y2],
                    'confidence': float(box.conf[0]),
                    'class_id': int(box.cls[0]),
                    'class_name': '野猪 boar'
                })
        return detections

    @staticmethod
    def draw_results(image, results, show_label=True):
        annotated = image.copy()
        for det in results:
            x1, y1, x2, y2 = [int(v) for v in det['box']]
            conf = det['confidence']
            label = f"{det['class_name']} {conf:.2f}"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
            if show_label:
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 8, y1), (0, 200, 0), -1)
                cv2.putText(annotated, label, (x1 + 4, y1 - 6),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        return annotated


# ─── 入口 ───────────────────────────────────────────────────────────────────


def main():
    root = Tk()
    app = BoarDetectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
