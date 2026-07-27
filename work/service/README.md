# 野猪检测 HTTP 服务

基于 YOLOv8 的野猪目标检测 HTTP 服务，支持 multipart 和纯二进制两种图片上传方式。

---

## 部署

### 环境要求

- Python 3.8+
- CentOS 7+ / Ubuntu 20.04+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 模型文件

模型路径在 `config.py` 中配置，默认为：

```
work/runs/detect/boar_detection/yolov8n_merged_final/weights/best.pt
```

可将模型文件复制到部署目录：

```bash
cp /path/to/best.pt /opt/boar-detection/
```

并修改 `config.py` 中的 `MODEL_PATH` 为绝对路径。

### 启动服务

```bash
# 开发测试
python app.py

# 生产部署（systemd）
sudo cp boar_detection.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now boar_detection

# 查看日志
sudo journalctl -u boar_detection -f
```

---

## API 接口

### POST /detect — multipart 方式

```bash
curl -X POST http://localhost:5000/detect \
  -F "image=@test_640.jpg"
```

### POST /detect/raw — 纯二进制方式

```bash
curl -X POST http://localhost:5000/detect/raw \
  -H "Content-Type: image/jpeg" \
  --data-binary @test_640.jpg
```

### GET /health — 健康检查

```bash
curl http://localhost:5000/health
```

---

## 配置说明

编辑 `config.py` 可修改：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| PORT | 5000 | 服务监听端口 |
| HOST | "0.0.0.0" | 服务监听地址 |
| MODEL_PATH | .../best.pt | 模型文件路径 |
| DEVICE | None | 推理设备 (cpu/cuda:0)，None 为自动选择 |
| CONFIDENCE_THRESHOLD | 0.25 | 置信度阈值 |
| IOU_THRESHOLD | 0.45 | NMS IoU 阈值 |
| INPUT_SIZE | 640 | 输入图片尺寸（固定） |
