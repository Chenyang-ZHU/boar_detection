#!/bin/bash
# ============================================================
# 野猪检测服务 · U盘一键安装脚本（给小白用）
# Boar Detection Service - One-click USB Installer (for non-technical users)
#
# 用法（小白）/ Usage (novice):
#     把本文件和 boar_centos7_offline.tar.gz 放在 U盘 根目录
#     Put this file and boar_centos7_offline.tar.gz in the USB root
#     → 插入目标 CentOS 7 机器 / Insert into target CentOS 7
#     → 双击 install_usb.sh / Double-click install_usb.sh
#     → 弹窗选「在终端中运行」/ Choose "Run in Terminal"
#     → 提示输入密码时，输管理员密码 / Enter admin password when prompted
#     → 等待出现「✅ 安装成功」/ Wait for "✅ 安装成功 (Install OK)"
#
# 前提 / Prerequisites:
#     U盘 必须是 ext4 格式（FAT32 无执行权限，双击失败）
#     USB must be ext4 (FAT32 has no exec permission, double-click fails)
#     目标 CentOS 7 (glibc 2.17)，已登录桌面 / CentOS 7, logged into desktop
# ============================================================
set -u

# ---------- 自动提权（非 root 则用 sudo 重新运行）/ Auto elevate (re-run with sudo if not root) ----------
if [ "$(id -u)" -ne 0 ]; then
  echo "需要管理员权限，请输入密码... / Admin password required, please enter..."
  exec sudo bash "$0" "$@"
fi

# ---------- 定位 U盘 里的离线包 / Locate the offline package on the USB ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARBALL="$SCRIPT_DIR/boar_centos7_offline.tar.gz"
MINICONDA_DIR="/opt/miniconda3"
DEPLOY_DIR="/opt/boar-detection"
PY="$MINICONDA_DIR/envs/boar/bin/python"

echo "======================================================"
echo "  野猪检测服务 · 一键安装"
echo "  Boar Detection Service - One-click Install"
echo "  离线包 / Package: $TARBALL"
echo "======================================================"

# ---------- 检查 / Check ----------
if [ ! -f "$TARBALL" ]; then
  echo "❌ 找不到离线包: $TARBALL"
  echo "   ❌ Package not found: $TARBALL"
  echo "   请确认 install_usb.sh 和 boar_centos7_offline.tar.gz 放在同一个文件夹（U盘根目录）"
  echo "   Please put install_usb.sh and boar_centos7_offline.tar.gz in the same folder (USB root)"
  echo "   按回车键关闭窗口 / Press Enter to close"
  read _
  exit 1
fi

# ---------- [1/5] 解压 / Extract ----------
echo ""
echo "===== [1/5] 解压离线包（约需 1-3 分钟）====="
echo "===== [1/5] Extracting package (~1-3 min) ====="
tar -xzf "$TARBALL" -C /opt
if [ ! -x "$PY" ]; then
  echo "❌ 解压失败或包损坏，请联系技术人员 / Extract failed or package corrupt, contact technical support"
  echo "   按回车键关闭窗口 / Press Enter to close"
  read _
  exit 1
fi
echo "✅ 已解压到 /opt / Extracted to /opt"

# ---------- [2/5] 配置开机自启 / Configure auto-start ----------
echo ""
echo "===== [2/5] 配置开机自启 ====="
echo "===== [2/5] Configuring auto-start ====="
sed -e "s|@PY@|$PY|g" \
    -e "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" \
    -e "s|@CONDA_LIB@|$MINICONDA_DIR/envs/boar/lib|g" \
    "$DEPLOY_DIR/boar_detection.service" > /etc/systemd/system/boar_detection.service
systemctl daemon-reload
systemctl enable --now boar_detection
echo "✅ 开机自启已配置 / Auto-start configured"

# ---------- [3/5] 一键诊断脚本 + 桌面图标 / Diagnostic tool + desktop icon ----------
echo ""
echo "===== [3/5] 安装诊断工具 ====="
echo "===== [3/5] Installing diagnostic tool ====="
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
  echo "✅ Diagnostic tool installed (desktop icon: Boar Service Diagnostic)"
fi

# ---------- [4/5] 健壮性加固 / Hardening ----------
echo ""
echo "===== [4/5] 健壮性加固 ====="
echo "===== [4/5] Hardening ====="
mkdir -p /etc/cron.d
# 健康探活（服务卡死自动重启）/ Health probe (auto-restart if hung)
if [ -f "$DEPLOY_DIR/boar_health.sh" ]; then
  cp "$DEPLOY_DIR/boar_health.sh" /usr/local/bin/boar_health.sh
  chmod +x /usr/local/bin/boar_health.sh
  echo "* * * * * root /usr/local/bin/boar_health.sh" > /etc/cron.d/boar_health
  chmod 644 /etc/cron.d/boar_health
fi
# 视频临时文件清理 / Temp video cleanup
echo "*/30 * * * * root find /tmp -maxdepth 1 -name 'boar_detect_*.mp4' -mmin +10 -delete" > /etc/cron.d/boar_tmp_clean
chmod 644 /etc/cron.d/boar_tmp_clean
# journald 日志限容 / Journal log limit
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/boar.conf
systemctl restart systemd-journald 2>/dev/null || true
echo "✅ 加固完成（自愈探活 + 日志限容 + 临时清理）/ Hardening done (self-heal + log limit + cleanup)"

# ---------- [5/5] 健康检查 / Health check ----------
echo ""
echo "===== [5/5] 启动服务并检查（最多等 40 秒）====="
echo "===== [5/5] Starting service & checking (up to 40s) ====="
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
  echo " ✅ Install OK! Service is running"
  echo ""
  echo "  服务地址 / Service URL: http://${IP:-本机IP/local}:5000"
  echo "  本机测试 / Local test:   http://127.0.0.1:5000"
  echo ""
  echo "  以后有问题：双击桌面「野猪服务诊断」生成报告"
  echo "  If issues: double-click 'Boar Service Diagnostic' on desktop for a report"
  echo "======================================================"
else
  echo " ⚠️ 服务未能就绪，请双击桌面「野猪服务诊断」查看原因"
  echo " ⚠️ Service not ready, double-click 'Boar Service Diagnostic' to check"
  echo "======================================================"
fi
echo ""
echo "按回车键关闭窗口 / Press Enter to close"
read _
