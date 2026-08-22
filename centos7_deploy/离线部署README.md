# 离线部署（无需网络）

把整个部署「下载的东西」打成一个包带走：**conda 环境（含 torch/ultralytics/flask 等全部依赖）+ 服务代码 + 模型 + systemd 单元**。新机器不需要再联网下载。

## 包从哪里来

在任意一台**已经跑过 `install_centos7.sh`** 的机器上（或本机用 docker 构建），把部署产物打包：

```bash
tar -czf boar_centos7_offline.tar.gz -C /opt miniconda3 boar-detection
```

> 打包前建议删除 `/opt/miniconda3/pkgs`（conda 包缓存，不参与运行，可省 1~2GB）与 `__pycache__`。
> 仓库 `centos7_deploy/` 里也提供了打包脚本（docker 构建用），产物即 `boar_centos7_offline.tar.gz`。

包内容（固定绝对路径，解压到相同路径即可用）：

| 路径 | 内容 |
|------|------|
| `/opt/miniconda3/envs/boar/` | Python 3.10 环境：torch 2.6.0 CPU / torchvision / ultralytics 8.4.114 / flask 等 |
| `/opt/boar-detection/` | app.py / detector.py / config.py / best.pt / boar_detection.service |

## 目标机器上部署

```bash
# 把 boar_centos7_offline.tar.gz 拷到目标机器（U 盘 / scp / 内网盘均可）
sudo bash deploy_offline.sh boar_centos7_offline.tar.gz
```

脚本自动完成：解压到 `/opt` → 装 systemd 单元 → 启动 → 健康检查（最多等 40s）。全程零网络。

## 验证

```bash
curl http://127.0.0.1:5000/health
curl -X POST http://127.0.0.1:5000/detect -F "image=@test.jpg"
```

## 对比安装版

| | 安装版 install_centos7.sh | 离线版 deploy_offline.sh |
|---|---|---|
| 目标机器需联网 | 是（Miniconda+conda-forge+torch 全要下载） | 否 |
| 耗时 | 10~20 分钟（取决于网速） | 1~3 分钟（解压为主） |
| 包体积 | — | ~1-2GB（tar.gz） |
| 磁盘占用 | ~4GB | ~4GB（解压后） |

> ⚠️ 离线包只面向 **同架构同系统**（x86_64 CentOS 7 / glibc 2.17）机器；不要拿到 Jetson（aarch64）上解压。
> ⚠️ 与安装版一致：`/opt/miniconda3`、`/opt/boar-detection` 是固定路径，解压路径不能改。
> ⚠️ **打包的 `boar_detection.service` 必须用含 `Environment=LD_LIBRARY_PATH=@CONDA_LIB@` 的新版**（CentOS 7 系统 libstdc++ 太老，PIL/torch 需要 conda 的 libstdc++，否则启动报 `GLIBCXX_3.4.21 not found`）。`deploy_offline.sh` 会自动把 `@CONDA_LIB@` 替换成 `/opt/miniconda3/envs/boar/lib`。
