#!/bin/bash
# ============================================================
# 野猪检测服务 · U盘一键安装脚本（给小白用）
#
# 用法（小白）:
#     把本文件和 boar_centos7_offline.tar.gz 放在 U盘 根目录
#     → 插入目标 CentOS 7 机器
#     → 双击 install_usb.sh
#     → 弹窗选「在终端中运行」
#     → 提示输入密码时，输管理员密码
#     → 等待出现「✅ 安装成功」即可
#
# 前提:
#     U盘 必须是 ext4 格式（FAT32 没有执行权限，双击会失败）
#     目标 CentOS 7 (glibc 2.17)，已登录桌面
# ============================================================
set -u

# ---------- 自动提权（非 root 则用 sudo 重新运行本脚本） ----------
if [ "$(id -u)" -ne 0 ]; then
  echo "需要管理员权限，请输入密码..."
  exec sudo bash "$0" "$@"
fi

# ---------- 定位 U盘 里的离线包 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARBALL="$SCRIPT_DIR/boar_centos7_offline.tar.gz"
MINICONDA_DIR="/opt/miniconda3"
DEPLOY_DIR="/opt/boar-detection"
PY="$MINICONDA_DIR/envs/boar/bin/python"

echo "======================================================"
echo "  野猪检测服务 · 一键安装"
echo "  离线包: $TARBALL"
echo "======================================================"

# ---------- 检查 ----------
if [ ! -f "$TARBALL" ]; then
  echo "❌ 找不到离线包: $TARBALL"
  echo "   请确认 install_usb.sh 和 boar_centos7_offline.tar.gz 放在同一个文件夹（U盘根目录）"
  echo "   按回车键关闭窗口"
  read _
  exit 1
fi

# ---------- [1/4] 解压 ----------
echo ""
echo "===== [1/4] 解压离线包（约需 1-3 分钟）====="
tar -xzf "$TARBALL" -C /opt
if [ ! -x "$PY" ]; then
  echo "❌ 解压失败或包损坏，请联系技术人员"
  echo "   按回车键关闭窗口"
  read _
  exit 1
fi
echo "✅ 已解压到 /opt"

# ---------- [2/4] 配置开机自启 ----------
echo ""
echo "===== [2/4] 配置开机自启 ====="
sed -e "s|@PY@|$PY|g" \
    -e "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" \
    -e "s|@CONDA_LIB@|$MINICONDA_DIR/envs/boar/lib|g" \
    "$DEPLOY_DIR/boar_detection.service" > /etc/systemd/system/boar_detection.service
systemctl daemon-reload
systemctl enable --now boar_detection
echo "✅ 开机自启已配置"

# ---------- [3/4] 一键诊断脚本 + 桌面图标 ----------
echo ""
echo "===== [3/4] 安装诊断工具 ====="
if [ -f "$DEPLOY_DIR/boar_diag.sh" ]; then
  cp "$DEPLOY_DIR/boar_diag.sh" /usr/local/bin/boar_diag.sh
  chmod +x /usr/local/bin/boar_diag.sh
  mkdir -p /usr/share/applications /root/Desktop
  if [ -f "$DEPLOY_DIR/boar_diag.desktop" ]; then
    cp "$DEPLOY_DIR/boar_diag.desktop" /usr/share/applications/ 2>/dev/null || true
    cp "$DEPLOY_DIR/boar_diag.desktop" /root/Desktop/ 2>/dev/null || true
    chmod +x /usr/share/applications/boar_diag.desktop /root/Desktop/boar_diag.desktop 2>/dev/null || true
  fi
  echo "✅ 诊断工具已装（桌面有「野猪服务诊断」图标）"
fi

# ---------- [4/4] 健康检查 ----------
echo ""
echo "===== [4/4] 启动服务并检查（最多等 40 秒）====="
ready=""
for i in $(seq 1 8); do
  if curl -s -m 3 http://127.0.0.1:5000/health >/dev/null 2>&1; then
    ready="yes"
    break
  fi
  sleep 5
done

echo ""
echo "======================================================"
if [ -n "$ready" ]; then
  IP=$(ip -4 addr show 2>/dev/null | grep -oP 'inet \K192\.168\.[0-9.]+' | head -1)
  echo " ✅ 安装成功！服务已启动"
  echo ""
  echo "  服务地址: http://${IP:-本机IP}:5000"
  echo "  本机测试: http://127.0.0.1:5000"
  echo ""
  echo "  以后有问题：双击桌面「野猪服务诊断」生成报告"
  echo "======================================================"
else
  echo " ⚠️ 服务未能就绪，请双击桌面「野猪服务诊断」查看原因"
  echo "======================================================"
fi
echo ""
echo "按回车键关闭窗口"
read _
