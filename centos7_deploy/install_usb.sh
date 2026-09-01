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
#     → 等待出现「✅ 安装成功」/ Wait for "✅ 安装成功 (Install OK)"
#
# 两种模式 / Two modes:
#     root 运行  → 系统级安装（装到 /opt，全用户可用）
#     Running as root → system install (/opt, all users)
#     非 root 运行 → 用户级安装（装到 ~/boar-detection，无需密码）
#     Running as non-root → user install (~/boar-detection, no password)
#
# 前提 / Prerequisites:
#     U盘 必须是 ext4 格式（FAT32 无执行权限，双击失败）
#     USB must be ext4 (FAT32 has no exec permission, double-click fails)
#     目标 CentOS 7 (glibc 2.17)，已登录桌面 / CentOS 7, logged into desktop
# ============================================================
set -u

# ---------- 定位 U盘 里的离线包 / Locate the offline package on the USB ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARBALL="$SCRIPT_DIR/boar_centos7_offline.tar.gz"

# ---------- 检测运行模式 / Detect install mode ----------
if [ "$(id -u)" -eq 0 ]; then
  MODE="system"
  MINICONDA_DIR="/opt/miniconda3"
  DEPLOY_DIR="/opt/boar-detection"
  CURL_AVAIL=1
else
  MODE="user"
  MINICONDA_DIR="$HOME/miniconda3"
  DEPLOY_DIR="$HOME/boar-detection"
fi
PY="$MINICONDA_DIR/envs/boar/bin/python"

echo "======================================================"
echo "  野猪检测服务 · 一键安装"
echo "  Boar Detection Service - One-click Install"
if [ "$MODE" = "system" ]; then
  echo "  模式 / Mode: 系统级 / System"
else
  echo "  模式 / Mode: 用户级（无需密码）/ User (no password)"
fi
echo "  安装目录 / Install to: $DEPLOY_DIR"
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
if [ "$MODE" = "system" ]; then
  tar -xzf "$TARBALL" -C /opt
else
  tar -xzf "$TARBALL" -C "$HOME"
fi
if [ ! -x "$PY" ]; then
  echo "❌ 解压失败或包损坏，请联系技术人员 / Extract failed or package corrupt, contact technical support"
  echo "   按回车键关闭窗口 / Press Enter to close"
  read _
  exit 1
fi
echo "✅ 已解压到 $DEPLOY_DIR / Extracted to $DEPLOY_DIR"

# ---------- [2/5] 配置开机自启 / Configure auto-start ----------
echo ""
echo "===== [2/5] 配置开机自启 ====="
echo "===== [2/5] Configuring auto-start ====="
if [ "$MODE" = "system" ]; then
  # 用户级 config 需覆盖 MODEL_PATH
  if [ -f "$DEPLOY_DIR/config.py" ]; then
    sed -i "s|MODEL_PATH = .*|MODEL_PATH = \"$DEPLOY_DIR/best.pt\"|" "$DEPLOY_DIR/config.py"
  fi
  sed -e "s|@PY@|$PY|g" \
      -e "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" \
      -e "s|@CONDA_LIB@|$MINICONDA_DIR/envs/boar/lib|g" \
      "$DEPLOY_DIR/boar_detection.service" > /etc/systemd/system/boar_detection.service
  systemctl daemon-reload
  systemctl enable --now boar_detection
else
  # 用户模式：覆盖 config MODEL_PATH 为 home 路径
  if [ -f "$DEPLOY_DIR/config.py" ]; then
    sed -i "s|MODEL_PATH = .*|MODEL_PATH = \"$DEPLOY_DIR/best.pt\"|" "$DEPLOY_DIR/config.py"
  fi
  # 生成用户 systemd 单元
  mkdir -p "$HOME/.config/systemd/user"
  sed -e "s|@PY@|$PY|g" \
      -e "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" \
      -e "s|@CONDA_LIB@|$MINICONDA_DIR/envs/boar/lib|g" \
      -e "s|WantedBy=multi-user.target|WantedBy=default.target|" \
      "$DEPLOY_DIR/boar_detection.service" > "$HOME/.config/systemd/user/boar_detection.service"
  systemctl --user daemon-reload
  systemctl --user enable --now boar_detection
  # 尝试开启 linger（开机免登录自启）；失败不影响登录后自启
  loginctl enable-linger "$(id -un)" 2>/dev/null || true
fi
echo "✅ 开机自启已配置 / Auto-start configured"

# ---------- [3/5] 一键诊断脚本 + 桌面图标 / Diagnostic tool + desktop icon ----------
echo ""
echo "===== [3/5] 安装诊断工具 ====="
echo "===== [3/5] Installing diagnostic tool ====="
if [ -f "$DEPLOY_DIR/boar_diag.sh" ]; then
  if [ "$MODE" = "system" ]; then
    cp "$DEPLOY_DIR/boar_diag.sh" /usr/local/bin/boar_diag.sh
    chmod +x /usr/local/bin/boar_diag.sh
    mkdir -p /usr/share/applications /root/Desktop
    [ -f "$DEPLOY_DIR/boar_diag.desktop" ] && cp "$DEPLOY_DIR/boar_diag.desktop" /usr/share/applications/ 2>/dev/null || true
    [ -f "$DEPLOY_DIR/boar_diag.desktop" ] && cp "$DEPLOY_DIR/boar_diag.desktop" /root/Desktop/ 2>/dev/null || true
    [ -f /usr/share/applications/boar_diag.desktop ] && chmod +x /usr/share/applications/boar_diag.desktop /root/Desktop/boar_diag.desktop 2>/dev/null || true
  else
    # 用户模式：诊断脚本留在部署目录，桌面图标放用户桌面
    chmod +x "$DEPLOY_DIR/boar_diag.sh"
    mkdir -p "$HOME/Desktop"
    [ -f "$DEPLOY_DIR/boar_diag.desktop" ] && cp "$DEPLOY_DIR/boar_diag.desktop" "$HOME/Desktop/" 2>/dev/null || true
    [ -f "$HOME/Desktop/boar_diag.desktop" ] && chmod +x "$HOME/Desktop/boar_diag.desktop" 2>/dev/null || true
  fi
  echo "✅ 诊断工具已装（桌面有「野猪服务诊断」图标）"
  echo "✅ Diagnostic tool installed (desktop icon: Boar Service Diagnostic)"
fi
# 拷贝测试图片到部署目录（供诊断工具做真实检出测试）
# Copy test image to deploy dir (for diagnostic real-detection test)
if [ -f "$SCRIPT_DIR/test_boar_640.jpg" ]; then
  cp "$SCRIPT_DIR/test_boar_640.jpg" "$DEPLOY_DIR/test_boar_640.jpg"
  echo "✅ 测试图片已拷贝 / Test image copied"
fi

# ---------- [4/5] 健壮性加固 / Hardening ----------
echo ""
echo "===== [4/5] 健壮性加固 ====="
echo "===== [4/5] Hardening ====="
if [ "$MODE" = "system" ]; then
  mkdir -p /etc/cron.d
  if [ -f "$DEPLOY_DIR/boar_health.sh" ]; then
    cp "$DEPLOY_DIR/boar_health.sh" /usr/local/bin/boar_health.sh
    chmod +x /usr/local/bin/boar_health.sh
    echo "* * * * * root /usr/local/bin/boar_health.sh" > /etc/cron.d/boar_health
    chmod 644 /etc/cron.d/boar_health
  fi
  echo "*/30 * * * * root find /tmp -maxdepth 1 -name 'boar_detect_*.mp4' -mmin +10 -delete" > /etc/cron.d/boar_tmp_clean
  chmod 644 /etc/cron.d/boar_tmp_clean
  mkdir -p /etc/systemd/journald.conf.d
  printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/boar.conf
  systemctl restart systemd-journald 2>/dev/null || true
else
  # 用户模式：健康探活用用户 crontab，日志写 home
  if [ -f "$DEPLOY_DIR/boar_health.sh" ]; then
    # 生成用户健康脚本（日志写 home，systemctl --user）
    sed -e "s|LOG=\"/var/log/boar_health.log\"|LOG=\"$DEPLOY_DIR/boar_health.log\"|" \
        -e "s|systemctl restart|systemctl --user restart|" \
        "$DEPLOY_DIR/boar_health.sh" > "$DEPLOY_DIR/boar_health_user.sh"
    chmod +x "$DEPLOY_DIR/boar_health_user.sh"
    # 加入用户 crontab
    ( crontab -l 2>/dev/null | grep -v "boar_health\|boar_detect_" ; \
      echo "* * * * * bash $DEPLOY_DIR/boar_health_user.sh" ; \
      echo "*/30 * * * * find /tmp -maxdepth 1 -name 'boar_detect_*.mp4' -mmin +10 -delete" ) | crontab -
  fi
fi
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
