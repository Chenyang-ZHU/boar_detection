# 野猪检测 (Boar Detection)

基于 YOLOv8 的野猪目标检测项目，单类别 `boar`，含检测服务与完整的数据集制作管线。

## 项目结构

```
boar_detection/
├── data/                    # 原始数据（不上传 GitHub，太大）
│   ├── 野猪/                # 手工照片（102 张）
│   └── 浦口4g-野猪{1,2,3}/  # 红外相机素材（1719 张图 + 815 个视频）
├── work/
│   ├── dataset.yaml         # 数据集配置（指向 ./merged）
│   ├── dataset/             # 早期自动标注数据集（train/val）
│   ├── merged/              # 最终数据集：images/ + labels/ + train/val/test.txt
│   ├── auto_label_new/      # 新预标注数据集（等人工审核）：
│   │   └── {frames,pukou_img,yewei_img}/all/{images,labels}/
│   ├── label_tool/          # 标注/审核 Web 服务（Flask，本地 :5000）
│   ├── prepare_dataset/     # 数据集制作脚本
│   │   ├── extract_frames.py   # 视频帧差自适应抽帧
│   │   ├── prelabel.py         # 现有模型预标注（ONNX Runtime，多进程）
│   │   ├── build_final.py      # 审核后按 70/15/15 划分 train/val/test
│   │   ├── manifest.csv        # 帧→源视频映射
│   │   └── negatives.csv       # 无检测图（负样本候选）
│   ├── runs/                # 训练记录（boar_detection/*/weights/best.pt）
│   └── service/             # 检测服务（app.py + detector.py）
├── centos7_deploy/          # CentOS 7 离线部署
└── README.md
```

## 数据集制作管线（新增）

1. **抽帧**：`python work/prepare_dataset/extract_frames.py`
   - 帧差自适应，815 个视频 → ~5300 帧，命名 `p{包}_PK{站点}_{视频}_f{帧}.jpg`
2. **预标注**：`python work/prepare_dataset/prelabel.py`
   - 用当前模型 `runs/detect/boar_detection/yolov8n_merged_final/weights/best.onnx`（ONNX Runtime CPU，比 torch 快 3-6 倍）
   - 处理未标注浦口图 + 野猪图 + 视频帧，输出 YOLO 标签到 `work/auto_label_new/`
   - 断点续跑；无检测图记入 `negatives.csv`；损坏源图记入 `unreadable.csv`
3. **人工审核**：`cd work/label_tool && python label_tool.py` → 浏览器 `http://localhost:5000`
   - 选数据集（frames/pukou_img/yewei_img），逐张改框/删框，`✅ 已审核 → merged` 并入 `work/merged`
4. **收尾划分**：`python work/prepare_dataset/build_final.py`
   - 审核完成后把 merged 按 70/15/15 写入 `train.txt / val.txt / test.txt`

## 训练

```bash
yolo train model=yolov8n.pt data=work/dataset.yaml
```

## 环境依赖

- Python 3.8+
- ultralytics（训练用）
- PyTorch（训练用）
- onnxruntime（预标注推理用，`pip install onnxruntime`）
- Flask（审核工具用）
