# 本地 Docker 验证离线部署（CentOS 7 模拟）

在本机用 Docker + **本机已有的 `centos:7` 镜像**（glibc 2.17），模拟真实 CentOS 7，验证离线包能解压、部署、起服务、推理。**仅用于本地验证**；真实机器直接用 `deploy_offline.sh` 部署（见 `离线部署README.md`）。

> 流程：启动容器 → `docker exec` 进入容器终端 → 依次运行 `prepare_shim.sh` 和 `deploy_offline.sh`。

## 1. 确认 Docker 与本机镜像

```bash
# Docker 服务是否在运行
systemctl is-active docker

# 本机已有 centos:7 镜像（列表里有即可）
docker images | grep centos

# 只有本机没有 centos:7 时才需要拉取（一般不用）：
# docker pull centos:7
```

## 2. 把离线包放到本机工作目录

```bash
# 若在 U 盘：插入后先找挂载点
lsblk
# Ubuntu 桌面一般自动挂载到 /run/media/<用户名>/<卷标>；未挂载则：
#   sudo mkdir -p /mnt/usb && sudo mount /dev/sdb1 /mnt/usb

# 拷到本机工作目录（把 <挂载点> 换成实际的；已在 ~/boar-centos7-offline 的跳过此步）
mkdir -p ~/boar-centos7-offline
cp <挂载点>/boar_centos7_offline.tar.gz ~/boar-centos7-offline/
cp <挂载点>/deploy_offline.sh ~/boar-centos7-offline/
cp <挂载点>/prepare_shim.sh ~/boar-centos7-offline/
ls -lh ~/boar-centos7-offline/
```

## 3. 启动容器（保持运行，先不部署）

```bash
docker rm -f boar-offline-demo 2>/dev/null
docker run -dit --name boar-offline-demo \
  -v ~/boar-centos7-offline:/bundle:ro \
  -p 15000:5000 \
  centos:7 \
  sleep 86400

# 确认容器已启动
docker ps --filter name=boar-offline-demo
```

## 4. 进入容器终端

```bash
docker exec -it boar-offline-demo bash
```

## 5. 在容器终端内部署

依次执行两步：先准备 systemctl shim（容器里没有 systemd，用它模拟），再跑离线部署：

```bash
# ① 准备 shim（生成 /usr/local/sbin/systemctl，模拟 systemd 启动服务）
bash /bundle/prepare_shim.sh

# ② 离线部署（解压到 /opt → 装 systemd 单元 → 启动服务 → 健康检查）
bash /bundle/deploy_offline.sh /bundle/boar_centos7_offline.tar.gz
```

看到 `✅ 离线部署完成！` 即部署成功，全程不需要联网。

## 6. 验证服务

**容器终端内**（服务跑在容器里的 5000 端口）：

```bash
curl -s http://127.0.0.1:5000/health
```

**宿主机**（容器把 5000 映射到宿主 15000）：

```bash
curl http://127.0.0.1:15000/health
curl -X POST http://127.0.0.1:15000/detect \
  -F "image=@/home/zcy/Documents/project/boar_detection/work/service/test_boar_640.jpg"
```

预期：`/health` 返回 `{"status":"ok","model_loaded":true,"device":"cpu",...}`；`/detect` 返回 `code:0` + 检测坐标。

## 7. 退出容器终端 / 清理

```bash
# 在容器终端里输入 exit 退出（服务仍继续运行，可随时再 exec 进入）
exit

# 之后想再进入容器终端
docker exec -it boar-offline-demo bash

# 验证完毕后清理容器
docker rm -f boar-offline-demo
```

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 部署脚本报 `systemctl: command not found` | 忘了先跑 `bash /bundle/prepare_shim.sh` |
| 部署脚本报错退出 | 在容器终端看 `❌` 报错行 |
| `/health` 一时不通 | 服务冷启动加载模型约 10s，等几秒再 `curl` |
| 想严格证明「零网络」 | 第 3 步 `docker run` 加 `--network none`（此时宿主 15000 端口不可用，验证改用容器内 `curl 127.0.0.1:5000/health`） |
