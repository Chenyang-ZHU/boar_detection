# 离线部署（无需网络）

把已打包好的离线包（conda 环境含全部依赖 + 服务代码 + 模型 + systemd 单元）解压到目标机即可用，全程**零网络**。

## 前置

- 已拿到离线包 `boar_centos7_offline.tar.gz`
- 目标 CentOS 7（x86_64，glibc 2.17），root / sudo

## 从 U 盘拷贝到本机

1. **插入 U 盘**。GNOME 桌面会自动挂载，打开文件管理器左侧可见 U 盘，挂载点一般是 `/run/media/<用户名>/<卷标>`。若没有自动挂载，手动挂载：

```bash
lsblk                            # 查看设备，例如 U 盘是 /dev/sdb1
sudo mkdir -p /mnt/usb
sudo mount /dev/sdb1 /mnt/usb    # 设备名按实际替换
```

2. **把离线包和部署脚本拷到本机磁盘**（U 盘上直接读 965MB 慢且易出错，先拷到本地再部署；下面以拷到 `/opt` 为例）：

```bash
# 自动挂载（GNOME 桌面）
sudo cp /run/media/<用户名>/<卷标>/boar_centos7_offline.tar.gz /opt/
sudo cp /run/media/<用户名>/<卷标>/deploy_offline.sh /opt/

# 手动挂载
sudo cp /mnt/usb/boar_centos7_offline.tar.gz /opt/
sudo cp /mnt/usb/deploy_offline.sh /opt/
```

3. **（可选）卸载 U 盘**：

```bash
sudo umount /mnt/usb    # 或卸载自动挂载点 /run/media/<用户名>/<卷标>
```

## 部署

```bash
# 磁盘余量检查：965MB 压缩包解压后约 4GB
df -h /opt

sudo bash /opt/deploy_offline.sh /opt/boar_centos7_offline.tar.gz
```

`deploy_offline.sh` 会自动把离线包解压到对应位置 `/opt/miniconda3` 与 `/opt/boar-detection`，然后安装 systemd 单元、启动服务并做健康检查（最多等 40s），全程**零网络**。

> 也可以不拷贝、直接从 U 盘部署：`sudo bash /run/media/<用户名>/<卷标>/deploy_offline.sh /run/media/<用户名>/<卷标>/boar_centos7_offline.tar.gz`

## 验证

```bash
curl http://127.0.0.1:5000/health
curl -X POST http://127.0.0.1:5000/detect -F "image=@test.jpg"
```

## 注意事项

> ⚠️ 只面向**同架构同系统**（x86_64 CentOS 7 / glibc 2.17）机器；不要拿到 Jetson（aarch64）上解压。
> ⚠️ `/opt/miniconda3`、`/opt/boar-detection` 是固定路径，解压路径不能改。
> ⚠️ 服务经 systemd 单元自带的 `LD_LIBRARY_PATH` 使用 conda 的 libstdc++（目标系统 libstdc++ 太老，脚本已处理）。
> ✅ **包内含生产服务器 waitress + 完整健壮性**（并发限流 429001 / 单请求超时 / 客户端断开中止 / 健康探活自愈），离线部署即加固版。离线包于 2026-08-23 重建并验证。
> ✅ **视频输出为 H.264 编码 + moov 前置（Web Fast Start）**：环境内含 imageio-ffmpeg（libx264），输出 `ftyp→moov→mdat`，浏览器可在线流式播放（2026-08-25 重建）。
