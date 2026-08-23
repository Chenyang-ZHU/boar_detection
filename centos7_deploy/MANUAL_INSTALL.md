# CentOS 7 手动安装指南

> 一步步手动部署，不依赖 `install_centos7.sh`。已在 **CentOS 7.9 / glibc 2.17 容器**里完整验证通过。
> 如果嫌麻烦，直接用 `install_centos7.sh`（一键版）。

---

## 0. 准备

```bash
# 需要 root
sudo -i

# 确认系统
cat /etc/redhat-release        # CentOS Linux release 7.x
ldd --version | head -1        # glibc 2.17（必须，否则下面的版本钉定不适用）

# 需要 wget/curl（二选一即可）
command -v wget || command -v curl || yum install -y wget curl
```

> ⚠️ CentOS 7 已于 2024-06 EOL，`yum` 源默认指向已下线的 `mirrorlist.centos.org`。
> 如果 `yum install` 报错，需把源切到 `vault.centos.org`：
> ```bash
> sed -i 's/^mirrorlist=/#mirrorlist=/g' /etc/yum.repos.d/CentOS-*.repo
> sed -i 's|^#baseurl=http://mirror.centos.org/centos|baseurl=http://vault.centos.org/centos|g' /etc/yum.repos.d/CentOS-*.repo
> yum clean all
> ```
> （vault 可能对部分网络返回 403，如装不了系统包不影响本部署，Miniconda/conda/pip 不依赖 yum。）

---

## 1. 安装 Miniconda（提供 Python 3.10）

> ⚠️ **必须钉 23.10.0-1，不要用 latest**：Miniconda 自 24.x 起要求 glibc ≥ 2.28，
> 在 CentOS 7 上会报 "Installer requires GLIBC >=2.28"。

```bash
wget -q https://repo.anaconda.com/miniconda/Miniconda3-py311_23.10.0-1-Linux-x86_64.sh -O /tmp/miniconda.sh
bash /tmp/miniconda.sh -b -p /opt/miniconda3
export PATH=/opt/miniconda3/bin:$PATH
```

## 2. 创建 conda 环境

```bash
conda create -y -n boar python=3.10 -c conda-forge
export PY=/opt/miniconda3/envs/boar/bin/python
export PIP=/opt/miniconda3/envs/boar/bin/pip
```

## 3. 安装依赖

**① 编译型依赖用 conda-forge**（保证 glibc 2.17 兼容，避开 pip wheel 的坑）：

```bash
conda install -y -n boar -c conda-forge \
  "numpy=1.26" opencv scipy pandas "matplotlib=3.7" \
  pillow pyyaml tqdm requests psutil seaborn
```

**② torch 用 CPU 版（钉 2.6.0，glibc 2.17 兼容的最高版）**：

```bash
$PIP install torch==2.6.0 torchvision==0.21.0 \
  --index-url https://download.pytorch.org/whl/cpu
```

**③ ultralytics + flask + waitress**（ultralytics 用 `--no-deps` 复用 conda 的 cv2/numpy；flask/waitress 正常装）：

```bash
$PIP install --no-deps ultralytics==8.4.114 py-cpuinfo ultralytics-thop
$PIP install "flask>=3.0"
$PIP install "waitress==3.0.2"
```

## 4. 部署服务文件

```bash
# 在仓库根目录下执行（复制服务代码 + 模型）
mkdir -p /opt/boar-detection
cp work/service/app.py work/service/detector.py /opt/boar-detection/
cp work/runs/detect/boar_detection/yolov8n_merged_final/weights/best.pt /opt/boar-detection/

# 写 CentOS 专用配置（或用 centos7_deploy/config.centos7.py）
cp centos7_deploy/config.centos7.py /opt/boar-detection/config.py
```

`config.centos7.py` 关键内容：`DEVICE="cpu"`、`MODEL_PATH="/opt/boar-detection/best.pt"`。

## 5. 手动启动（先验证）

> ⚠️ **关键：必须设置 LD_LIBRARY_PATH**。CentOS 7 系统 libstdc++ 只支持到 GLIBCXX_3.4.19，
> PIL/torch 需要 GLIBCXX_3.4.21+，不设置会报
> `ImportError: /lib64/libstdc++.so.6: version 'GLIBCXX_3.4.21' not found`。

```bash
export LD_LIBRARY_PATH=/opt/miniconda3/envs/boar/lib:$LD_LIBRARY_PATH
cd /opt/boar-detection
nohup /opt/miniconda3/envs/boar/bin/python app.py > /tmp/boar.log 2>&1 &
```

验证：

```bash
curl http://127.0.0.1:5000/health
# {"device":"cpu","model":"yolov8n_merged_final","model_loaded":true,"status":"ok",...}

curl -X POST http://127.0.0.1:5000/detect -F "image=@test.jpg"    # 返回坐标 JSON
curl -X POST http://127.0.0.1:5000/detect/video/coords -F "video=@test.mp4"   # 逐帧坐标
curl -o out.mp4 -X POST http://127.0.0.1:5000/detect/video -F "video=@test.mp4"  # 画框视频
```

## 6. systemd 开机自启

写 `/etc/systemd/system/boar_detection.service`：

```ini
[Unit]
Description=Boar Detection HTTP Service (CentOS 7)
After=network.target

[Service]
Type=simple
User=root
# 必须指向 conda 环境 lib（libstdc++ 版本问题）
Environment=LD_LIBRARY_PATH=/opt/miniconda3/envs/boar/lib
WorkingDirectory=/opt/boar-detection
ExecStart=/opt/miniconda3/envs/boar/bin/python /opt/boar-detection/app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now boar_detection
# 查看日志
journalctl -u boar_detection -f
```

---

## 7. 常见问题

| 现象 | 原因 / 解决 |
|------|------------|
| `ImportError: GLIBCXX_3.4.21 not found` | 没设 `LD_LIBRARY_PATH`，见第 5 步 |
| Miniconda 安装报 `requires GLIBC >=2.28` | 用了 latest，必须用 `23.10.0-1` |
| `pip install torch` 装不上 | 版本太高（≥2.7 需 glibc 2.28），钉 `2.6.0` |
| `pip install` 拉最新 numpy/opencv 失败 | 钉旧版：`numpy==1.26.4`、`opencv-python==4.9.0.80` |
| 视频接口超时 | CPU 逐帧 ~50-150ms，长视频建议超时 240s+ |
