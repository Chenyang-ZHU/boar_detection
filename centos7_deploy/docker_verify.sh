#!/bin/bash
# ============================================================
# 野猪检测服务 · Docker 验证脚本
# 用 centos:7 容器模拟目标机器，验证离线包能部署 + 服务能跑。
#
# 用法:
#     bash docker_verify.sh [方法] [离线包路径]
#
# 参数:
#     方法      默认 deploy（用 deploy_offline.sh 部署）
#               可传 usb （用 install_usb.sh 模拟 U盘 一键安装）
#     离线包路径 默认 /home/zcy/boar-centos7-offline/boar_centos7_offline.tar.gz
#
# 前提:
#     - 本机装有 docker + centos:7 镜像
#     - 需要 centos7_deploy/ 下的 prepare_shim.sh
# ============================================================
set -euo pipefail

METHOD="${1:-deploy}"
OFFLINE="${2:-/home/zcy/boar-centos7-offline/boar_centos7_offline.tar.gz}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER="boar-docker-verify"

echo "=== 参数 ==="
echo "  验证方法: $METHOD"
echo "  离线包:   $OFFLINE"
echo ""

# ---------- 准备模拟 U盘 / 挂载目录 ----------
WORKDIR="/tmp/boar_docker_verify"
rm -rf "$WORKDIR"; mkdir -p "$WORKDIR"
cp "$OFFLINE" "$WORKDIR/"
cp "$SCRIPT_DIR/prepare_shim.sh" "$WORKDIR/"

# 模拟 U盘 结构（install_usb 方式用）
if [ "$METHOD" = "usb" ]; then
  cp "$SCRIPT_DIR/install_usb.sh" "$WORKDIR/"
  echo "✅ 已准备 U盘 模拟目录: $WORKDIR"
else
  cp "$SCRIPT_DIR/deploy_offline.sh" "$WORKDIR/"
  echo "✅ 已准备部署目录: $WORKDIR"
fi

# ---------- 启动容器 ----------
echo ""
echo "=== 启动 centos:7 容器 ==="
docker rm -f "$CONTAINER" 2>/dev/null || true
docker run -d --name "$CONTAINER" -v "$WORKDIR":/bundle:ro centos:7 sleep infinity
echo "容器已启动: $CONTAINER"

# ---------- 装 systemctl 垫片（容器无 systemd） ----------
echo ""
echo "=== 装 systemctl 垫片 ==="
docker exec "$CONTAINER" bash /bundle/prepare_shim.sh 2>&1 | tail -1

# ---------- 执行部署 ----------
echo ""
echo "=== 执行部署 ($METHOD) ==="
if [ "$METHOD" = "usb" ]; then
  docker exec "$CONTAINER" bash /bundle/install_usb.sh 2>&1 | grep -E "=====|✅ 安装成功|✅ 已解压|❌" | head -15
else
  docker exec "$CONTAINER" bash -c 'cd /bundle && bash deploy_offline.sh boar_centos7_offline.tar.gz' 2>&1 | grep -E "=====|✅ 离线部署完成|❌|已解压" | head -12
fi

# ---------- 验证接口 + 编码 ----------
echo ""
echo "=== 验证服务接口 + 视频编码 ==="
docker exec "$CONTAINER" bash -c '
LD_LIBRARY_PATH=/opt/miniconda3/envs/boar/lib /opt/miniconda3/envs/boar/bin/python - << "EOF"
import requests, struct, numpy as np, cv2
BASE = "http://127.0.0.1:5000"

# /health
d = requests.get(BASE+"/health", timeout=10).json()
print("  /health:", d["status"], d["device"])

# 生成测试图 + 视频
img = np.full((640,640,3), 128, np.uint8)
ok, buf = cv2.imencode(".jpg", img)
w = cv2.VideoWriter("/tmp/t.mp4", cv2.VideoWriter_fourcc(*"mp4v"), 5, (640,640))
for _ in range(5): w.write(img)
w.release()

# /detect
r = requests.post(BASE+"/detect", files={"image":("t.jpg", buf.tobytes(), "image/jpeg")}, timeout=30)
print("  /detect: code=%s" % r.json()["code"])

# /video/coords
r = requests.post(BASE+"/detect/video/coords", files={"video":open("/tmp/t.mp4","rb")}, timeout=60)
d = r.json()["data"]
print("  /video/coords: %s帧 total=%s max=%s" % (d["frame_count"], d["total_detections"], d["max_detections"]))

# /video 编码检查
r = requests.post(BASE+"/detect/video", files={"video":open("/tmp/t.mp4","rb")}, timeout=120)
b = r.content
print("  /video: H264=%s mp4v=%s X-Boar-Count=%s" % (b.count(b"avcC"), b.count(b"mp4v"), r.headers.get("X-Boar-Count")))
pos, ats = 0, []
while pos < len(b) and len(ats) < 6:
    if pos+8 > len(b): break
    s, t = struct.unpack(">I4s", b[pos:pos+8])
    if s == 0: break
    ats.append(t.decode("latin1")); pos += s
moov_front = "moov" in ats and (ats.index("moov") < ats.index("mdat") if "mdat" in ats else ats.index("moov") < 2)
print("  atom=%s moov前置=%s" % ("->".join(ats[:4]), "OK" if moov_front else "FAIL"))
EOF
'

# ---------- 清理 ----------
echo ""
echo "=== 清理 ==="
docker rm -f "$CONTAINER" 2>/dev/null
echo "容器已清理"
echo ""
echo "======================================================"
echo " ✅ 验证完成！全部 ✅ 即离线包可用"
echo " 想换方法：bash docker_verify.sh usb（模拟U盘安装）"
echo "======================================================"
