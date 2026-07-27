
import os
import random
import shutil
from pathlib import Path
from ultralytics import YOLO

# 设置路径
BASE_DIR = Path(__file__).resolve().parent  # work 目录
DATA_DIR = BASE_DIR.parent / "data" / "野猪"
WORK_DIR = BASE_DIR
DATASET_DIR = WORK_DIR / "dataset"

# 创建数据集目录结构
for split in ["train", "val"]:
    for folder in ["images", "labels"]:
        (DATASET_DIR / split / folder).mkdir(parents=True, exist_ok=True)

# 获取所有图片
image_files = list(DATA_DIR.glob("*.jpg")) + list(DATA_DIR.glob("*.JPG"))
image_files.sort()

print(f"找到 {len(image_files)} 张图片")

# 随机打乱并分割
random.seed(42)
random.shuffle(image_files)
split_idx = len(image_files) // 2
train_files = image_files[:split_idx]
val_files = image_files[split_idx:]

print(f"训练集: {len(train_files)} 张")
print(f"验证集: {len(val_files)} 张")

# 加载最强的YOLOv8模型
print("\n加载 YOLOv8x 模型...")
model = YOLO("yolov8x.pt")

# COCO数据集中动物相关的类别
# 我们用这个来检测可能的野猪（可能会检测成动物类）
ANIMAL_CLASSES = {
    16: "bird",
    17: "cat",
    18: "dog",
    19: "horse",
    20: "sheep",
    21: "cow",
    22: "elephant",
    23: "bear",
    24: "zebra",
    25: "giraffe",
}

def auto_label(image_files, split_name):
    """自动标注图片"""
    print(f"\n开始标注 {split_name} 集...")
    
    for idx, img_path in enumerate(image_files):
        print(f"[{idx+1}/{len(image_files)}] 处理: {img_path.name}")
        
        # 用YOLOv8x预测
        results = model(img_path, conf=0.1)  # 低置信度阈值，捕获更多目标
        
        # 复制图片
        dst_img = DATASET_DIR / split_name / "images" / img_path.name
        shutil.copy(img_path, dst_img)
        
        # 创建标注文件
        label_path = DATASET_DIR / split_name / "labels" / (img_path.stem + ".txt")
        
        with open(label_path, "w") as f:
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        # 只要是动物类，我们都标注为野猪（class 0）
                        if cls_id in ANIMAL_CLASSES:
                            # 获取归一化坐标
                            x1, y1, x2, y2 = box.xyxyn[0].tolist()
                            # 转换为 YOLO 格式: class_id x_center y_center width height
                            x_center = (x1 + x2) / 2
                            y_center = (y1 + y2) / 2
                            width = x2 - x1
                            height = y2 - y1
                            f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
        
        print(f"  保存到: {dst_img}")
        print(f"  标注文件: {label_path}")

# 执行自动标注
auto_label(train_files, "train")
auto_label(val_files, "val")

# 创建 dataset.yaml
yaml_content = f"""
path: {DATASET_DIR}
train: train/images
val: val/images

names:
  0: boar
"""

yaml_path = WORK_DIR / "dataset.yaml"
yaml_path.write_text(yaml_content)
print(f"\n数据集配置已保存: {yaml_path}")
print("\n✅ 自动标注完成！")

