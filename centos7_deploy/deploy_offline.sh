#!/bin/bash
# ============================================================
# 野猪检测服务 离线一键部署（无需网络）
#
# 用法:
#     sudo bash deploy_offline.sh [离线包路径]
#     （默认找当前目录下的 boar_centos7_offline.tar.gz）
#
# 前置:
#   - 已拿到 boar_centos7_offline.tar.gz（内含 miniconda3 环境 + 服务文件 + 模型）
#   - 目标 CentOS 7 (glibc 2.17)，root / sudo
#   - 不需要网络：conda 环境、torch/ultralytics/flask 等全部依赖都在包里
#
# 脚本自动:
#   1. 解压离线包到 /opt（生成 /opt/miniconda3 与 /opt/boar-detection）
#   2. 安装 systemd 开机自启单元
#   3. 启动服务并健康检查（最多等 40s）
# ============================================================
set -euo pipefail

TARBALL="${1:-boar_centos7_offline.tar.gz}"
MINICONDA_DIR="/opt/miniconda3"
DEPLOY_DIR="/opt/boar-detection"
PY="$MINICONDA_DIR/envs/boar/bin/python"

# 新版拆包（优先）：boar_env.tar.gz + boar_scripts.tar.gz 与脚本同目录；兼容旧版单包
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_TAR="$SCRIPT_DIR/boar_env.tar.gz"
SCRIPTS_TAR="$SCRIPT_DIR/boar_scripts.tar.gz"

# ---------- 检查 ----------
if [ "$(id -u)" -ne 0 ]; then
  echo "❌ 请用 root 运行: sudo bash deploy_offline.sh"
  exit 1
fi
if [ ! -f "$ENV_TAR" ] && [ ! -f "$TARBALL" ]; then
  echo "❌ 找不到环境包（需 boar_env.tar.gz，或旧版 boar_centos7_offline.tar.gz）"
  echo "   用法: sudo bash deploy_offline.sh [离线包路径]"
  exit 1
fi
if [ ! -f "$SCRIPTS_TAR" ] && [ ! -f "$TARBALL" ]; then
  echo "❌ 找不到脚本包（需 boar_scripts.tar.gz，或旧版 boar_centos7_offline.tar.gz）"
  exit 1
fi

# ---------- [1/4] 解压（环境 + 脚本） ----------
echo "===== [1/4] 解压（环境 + 脚本）到 /opt ====="
# 环境：python 已存在则跳过（支持重复部署/升级）
if [ -x "$PY" ]; then
  echo "✅ 环境已存在，跳过解压: $PY"
elif [ -f "$ENV_TAR" ]; then
  tar -xzf "$ENV_TAR" -C /opt
elif [ -f "$TARBALL" ]; then
  tar -xzf "$TARBALL" -C /opt miniconda3
fi
# 脚本：总是覆盖解压（保证拿到最新版本）
if [ -f "$SCRIPTS_TAR" ]; then
  tar -xzf "$SCRIPTS_TAR" -C /opt
elif [ -f "$TARBALL" ]; then
  tar -xzf "$TARBALL" -C /opt boar-detection
fi
if [ ! -x "$PY" ]; then
  echo "❌ 解压后未找到环境 $PY，包可能损坏或路径不符"
  exit 1
fi
if [ ! -f "$DEPLOY_DIR/boar_detection.service" ]; then
  echo "❌ 解压后未找到 $DEPLOY_DIR/boar_detection.service"
  echo "   离线包需在跑过 install_centos7.sh 的机器上打包，其 /opt/boar-detection 应自带 systemd 单元文件"
  exit 1
fi
echo "✅ 已解压: $MINICONDA_DIR 与 $DEPLOY_DIR"

# ---------- [2/4] systemd ----------
echo "===== [2/4] 安装 systemd 开机自启 ====="
# @CONDA_LIB@：CentOS 7 系统 libstdc++ 太老（最高 GLIBCXX_3.4.19），
# 必须用 conda 环境的 libstdc++（PIL/torch 需要 GLIBCXX_3.4.21+），否则报 "GLIBCXX_3.4.21 not found"
sed -e "s|@PY@|$PY|g" \
    -e "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" \
    -e "s|@CONDA_LIB@|$MINICONDA_DIR/envs/boar/lib|g" \
    "$DEPLOY_DIR/boar_detection.service" > /etc/systemd/system/boar_detection.service
systemctl daemon-reload
systemctl enable --now boar_detection
echo "✅ systemd 单元已启用"

# ---------- [2.5/4] 健壮性加固（探活自愈 + 日志限容 + 临时文件清理） ----------
echo "===== [2.5/4] 健壮性加固 ====="
if [ -f "$DEPLOY_DIR/boar_health.sh" ]; then
  mkdir -p /etc/cron.d
  cp "$DEPLOY_DIR/boar_health.sh" /usr/local/bin/boar_health.sh
  chmod +x /usr/local/bin/boar_health.sh
  cat > /etc/cron.d/boar_health << 'EOF'
* * * * * root /usr/local/bin/boar_health.sh
EOF
  chmod 644 /etc/cron.d/boar_health
  echo "✅ 健康探活 cron 已装"
fi
cat > /etc/cron.d/boar_tmp_clean << 'EOF'
*/30 * * * * root find /tmp -maxdepth 1 -name 'boar_detect_*.mp4' -mmin +10 -delete
EOF
chmod 644 /etc/cron.d/boar_tmp_clean
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/boar.conf
systemctl restart systemd-journald 2>/dev/null || true
echo "✅ 加固完成"
# 一键诊断脚本 + 桌面图标（与 install_usb.sh 一致）
if [ -f "$DEPLOY_DIR/boar_diag.sh" ]; then
  cp "$DEPLOY_DIR/boar_diag.sh" /usr/local/bin/boar_diag.sh
  chmod +x /usr/local/bin/boar_diag.sh
  mkdir -p /usr/share/applications /root/Desktop
  if [ -f "$DEPLOY_DIR/boar_diag.desktop" ]; then
    cp "$DEPLOY_DIR/boar_diag.desktop" /usr/share/applications/ 2>/dev/null || true
    cp "$DEPLOY_DIR/boar_diag.desktop" /root/Desktop/ 2>/dev/null || true
    chmod +x /usr/share/applications/boar_diag.desktop /root/Desktop/boar_diag.desktop 2>/dev/null || true
  fi
  echo "✅ 诊断工具已装（/usr/local/bin/boar_diag.sh + 桌面图标）"
fi

# ---------- [3/4] 健康检查 ----------
echo "===== [3/4] 健康检查（最多等 40s：冷启动需加载模型）====="
ready=""
for i in $(seq 1 8); do
  if curl -s -m 3 http://127.0.0.1:5000/health; then
    echo ""
    ready="yes"
    break
  fi
  sleep 5
done
[ -n "$ready" ] || { echo "❌ 服务未就绪，请检查: systemctl status boar_detection"; exit 1; }

# ---------- 完成 ----------
echo ""
echo "=========================================="
echo " ✅ 离线部署完成！"
echo " 局域网地址: http://<本机IP>:5000"
echo " 测试命令:"
echo "   curl http://<本机IP>:5000/health"
echo "   curl -X POST http://<本机IP>:5000/detect -F 'image=@test.jpg'"
echo "=========================================="
