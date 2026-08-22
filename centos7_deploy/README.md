# CentOS 7 部署说明

野猪检测服务在 **CentOS 7（无 GPU，CPU 推理）** 上的部署文件。

## 背景结论（为什么这么做）

| 项 | 说明 |
|----|------|
| 显卡 | `llvmpipe`（软件渲染，无 CUDA）→ 配置用 **`DEVICE="cpu"`** |
| Python | CentOS 7 原生只有 2.7/3.6 → 需要 **Python 3.8+**（本方案用 Miniconda 装 3.10） |
| glibc | CentOS 7 是 glibc 2.17 → **torch 只能装 ≤2.6.0**，numpy≤1.26、opencv≤4.9（更高版本需 glibc 2.28，装不上） |
| 服务代码 | **零改动**，与 Jetson 上同一套 app.py/detector.py |

## 目录内容

| 文件 | 作用 |
|------|------|
| `install_centos7.sh` | **一键部署脚本**（推荐）：装 Miniconda + 依赖 + 部署 + systemd |
| `requirements-centos7.txt` | pip 方式依赖清单（钉死 glibc 2.17 兼容版本），作为替代安装路线 |
| `config.centos7.py` | CentOS 专用配置（`DEVICE="cpu"`、`MODEL_PATH=/opt/boar-detection/best.pt`） |
| `boar_detection.service` | systemd 开机自启单元 |

## 一键部署（推荐）

```bash
# 1. 把整个仓库（含 centos7_deploy/）拷到 CentOS 7 机器
# 2. 进入目录执行
cd centos7_deploy
sudo bash install_centos7.sh
```

脚本自动完成：
1. 安装 Miniconda（Python 3.10）
2. conda-forge 装编译依赖（numpy/opencv/scipy/pandas/matplotlib... 全 glibc 兼容）
3. pip 装 torch 2.6.0 CPU 版 + torchvision 0.21.0（PyTorch CPU 源）
4. pip 装 ultralytics 8.4.114 + flask
5. 部署代码 + 模型到 `/opt/boar-detection`
6. 配置 systemd 开机自启

## 验证

```bash
curl http://127.0.0.1:5000/health
curl -X POST http://127.0.0.1:5000/detect -F "image=@test.jpg"
curl -X POST http://127.0.0.1:5000/detect/video/coords -F "video=@test.mp4"
```

## pip 替代路线（不装 Miniconda，自备 Python 3.10）

```bash
python3.10 -m venv /opt/boar-detection/venv
source /opt/boar-detection/venv/bin/activate
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-centos7.txt
# 然后手动拷贝服务文件 + config.centos7.py + systemd（见脚本后半段）
```

## ⚠️ 性能预期（CPU vs Jetson GPU）

- 单图推理：**~100-150ms**（和原 CentOS 方案一致）
- 视频逐帧：**~100-150ms/帧**，30s@30fps 视频约需 **1.5-2 分钟**
- 调用方超时建议：图像 30s，视频 **240s+**

## ⚠️ 注意事项

- **Miniconda 钉死 23.10.0-1**：`latest` 自 24.x 起要求 glibc >= 2.28，在 CentOS 7 (glibc 2.17) 上会报 "Installer requires GLIBC >=2.28"，装不上。脚本已钉死 `Miniconda3-py311_23.10.0-1-Linux-x86_64.sh`，不要改回 latest。
- **不要升级依赖**：`torch<2.7`、`numpy<2`、`opencv<4.10`，否则 glibc 不满足装不上
- **libstdc++ 必须用 conda 的**：CentOS 7 系统自带的 `libstdc++.so.6` 最高只支持 GLIBCXX_3.4.19，PIL/torch 需要 GLIBCXX_3.4.21+。脚本/systemd 已通过 `Environment=LD_LIBRARY_PATH=/opt/miniconda3/envs/boar/lib` 解决；**手动启动服务时也必须加**：`export LD_LIBRARY_PATH=/opt/miniconda3/envs/boar/lib`
- 模型文件需放在 `/opt/boar-detection/best.pt`（脚本会自动拷）
- 局域网直接访问 `http://<本机IP>:5000`；如需公网，可在本机配 ngrok/其他隧道（见 `work/service/公网测试指南.md`）
