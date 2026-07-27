# 野猪检测 (Boar Detection)

基于 YOLOv8 的野猪目标检测项目。

## 项目结构

```
boar_detection/
├── data/                    # 原始数据（不上传 GitHub，太大）
├── work/
│   ├── auto_label.py        # 自动标注脚本
│   ├── dataset.yaml         # 数据集配置文件
│   ├── dataset/             # 初始标注数据集（标签文件）
│   │   ├── train/labels/
│   │   └── val/labels/
│   ├── merged/              # 合并后的最终数据集
│   │   ├── labels/          # 标注文件
│   │   ├── train.txt
│   │   ├── val.txt
│   │   └── test.txt
│   └── runs/                # 训练记录与配置
│       └── detect/boar_detection/
├── .gitignore
└── README.md
```

## 使用说明

1. 将原始图片放入 `data/野猪/` 目录
2. 运行自动标注：`python work/auto_label.py`
3. 使用 YOLOv8 训练：`yolo train model=yolov8n.pt data=work/dataset.yaml`

## 环境依赖

- Python 3.8+
- ultralytics
- PyTorch
