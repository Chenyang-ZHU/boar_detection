#!/bin/bash
# ============================================================
# 野猪检测服务 · U盘一键安装脚本（给小白用）
# Boar Detection Service - One-click USB Installer (for non-technical users)
#
# 用法（小白）/ Usage (novice):
#     把本文件和 boar_env.tar.gz、boar_scripts.tar.gz 放在 U盘 根目录
#     Put this file + boar_env.tar.gz + boar_scripts.tar.gz in the USB root
#     → 插入目标 CentOS 7 机器 / Insert into target CentOS 7
#     → 双击 install_usb.sh / Double-click install_usb.sh
#     → 弹窗选「在终端中运行」/ Choose "Run in Terminal"
#     → 等待出现「✅ 安装成功」/ Wait for "✅ 安装成功 (Install OK)"
#     兼容旧版单包 boar_centos7_offline.tar.gz / Back-compat with legacy single package
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
# 新版拆包：环境(一次性构建，少变) + 脚本(每次改动重建)；兼容旧版单包
ENV_TAR="$SCRIPT_DIR/boar_env.tar.gz"
SCRIPTS_TAR="$SCRIPT_DIR/boar_scripts.tar.gz"
OLD_TAR="$SCRIPT_DIR/boar_centos7_offline.tar.gz"

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

# ---------- 安装日志：写到脚本同级目录，方便甲方拷贝回传 ----------
# Install log: written next to this script so the novice can copy/send it back
LOG_FILE="$SCRIPT_DIR/install_log.txt"
if ! touch "$LOG_FILE" 2>/dev/null; then
  LOG_FILE="$HOME/install_log.txt"
  touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/tmp/install_log.txt"
fi
exec > >(tee -a "$LOG_FILE") 2>&1
echo "[$(date '+%F %T')] ===== 野猪检测服务安装日志开始 / Install log start ====="
echo "  日志文件 / Log file: $LOG_FILE"

echo "======================================================"
echo "  野猪检测服务 · 一键安装"
echo "  Boar Detection Service - One-click Install"
if [ "$MODE" = "system" ]; then
  echo "  模式 / Mode: 系统级 / System"
else
  echo "  模式 / Mode: 用户级（无需密码）/ User (no password)"
fi
echo "  安装目录 / Install to: $DEPLOY_DIR"
if [ -f "$ENV_TAR" ] && [ -f "$SCRIPTS_TAR" ]; then
  echo "  离线包 / Package: boar_env.tar.gz + boar_scripts.tar.gz (拆包)"
elif [ -f "$OLD_TAR" ]; then
  echo "  离线包 / Package: boar_centos7_offline.tar.gz (旧单包)"
else
  echo "  离线包 / Package: 未找到 / not found"
fi
echo "======================================================"

# ---------- 检查 / Check ----------
if [ ! -f "$ENV_TAR" ] && [ ! -f "$SCRIPTS_TAR" ] && [ ! -f "$OLD_TAR" ]; then
  echo "❌ 找不到离线包（需 boar_env.tar.gz + boar_scripts.tar.gz，或旧版 boar_centos7_offline.tar.gz）"
  echo "   ❌ Package not found (need boar_env.tar.gz + boar_scripts.tar.gz, or legacy boar_centos7_offline.tar.gz)"
  echo "   请确认安装包文件与 install_usb.sh 放在同一个文件夹（U盘根目录）"
  echo "   Please put package files and install_usb.sh in the same folder (USB root)"
  echo "   按回车键关闭窗口 / Press Enter to close"
  read _
  exit 1
fi

# ---------- [1/5] 解压 / Extract ----------
# 拆包格式：boar_env.tar.gz（环境，~1GB，一次性构建）+ boar_scripts.tar.gz（脚本，~7MB，每次改动重建）
# 兼容旧版单包 boar_centos7_offline.tar.gz
if [ "$MODE" = "system" ]; then
  BASE_DIR="/opt"
else
  BASE_DIR="$HOME"
fi
echo ""
echo "===== [1/5] 解压（环境 + 脚本）====="
echo "===== [1/5] Extracting (env + scripts) ====="

# 环境：python 已存在则跳过（支持重复安装/升级，省 1-3 分钟）
# 注意：若以后更新了依赖版本，需删除旧环境或临时用旧单包强制重解压
if [ -x "$PY" ]; then
  echo "✅ 环境已存在，跳过解压: $PY"
elif [ -f "$ENV_TAR" ]; then
  echo "解压环境包 boar_env.tar.gz（约 1-3 分钟）..."
  tar -xzf "$ENV_TAR" -C "$BASE_DIR"
elif [ -f "$OLD_TAR" ]; then
  echo "解压环境（旧单包 boar_centos7_offline.tar.gz）..."
  tar -xzf "$OLD_TAR" -C "$BASE_DIR" miniconda3
else
  echo "❌ 找不到环境包 / Environment package not found"
  echo "   按回车键关闭窗口 / Press Enter to close"
  read _
  exit 1
fi

# 脚本：总是覆盖解压（保证拿到最新版本）
if [ -f "$SCRIPTS_TAR" ]; then
  tar -xzf "$SCRIPTS_TAR" -C "$BASE_DIR"
elif [ -f "$OLD_TAR" ]; then
  tar -xzf "$OLD_TAR" -C "$BASE_DIR" boar-detection
else
  echo "❌ 找不到脚本包 / Scripts package not found"
  echo "   按回车键关闭窗口 / Press Enter to close"
  read _
  exit 1
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
  # 清失败状态：重复安装/修复时保证能重新拉起（傻瓜式：再双击一次即可自愈）
  systemctl reset-failed boar_detection 2>/dev/null || true
  systemctl enable --now boar_detection
else
  # 用户模式：覆盖 config MODEL_PATH 为 home 路径
  if [ -f "$DEPLOY_DIR/config.py" ]; then
    sed -i "s|MODEL_PATH = .*|MODEL_PATH = \"$DEPLOY_DIR/best.pt\"|" "$DEPLOY_DIR/config.py"
  fi
  # 用户级自启：不依赖 systemd（双击启动的环境常缺 XDG_RUNTIME_DIR，systemctl --user 会连不上）。
  # 采用三保险：start.sh 启动脚本 + 桌面开机自启 + systemd 尽力尝试。

  # ① 生成用户 systemd 单元（尽力使用；不可用也不影响，靠③④启动）
  mkdir -p "$HOME/.config/systemd/user"
  # ⚠️ 必须删掉 User=root：用户管理器无权把服务切换成 root，留着单元起不来。
  sed -e "/^User=/d" \
      -e "s|@PY@|$PY|g" \
      -e "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" \
      -e "s|@CONDA_LIB@|$MINICONDA_DIR/envs/boar/lib|g" \
      -e "s|WantedBy=multi-user.target|WantedBy=default.target|" \
      "$DEPLOY_DIR/boar_detection.service" > "$HOME/.config/systemd/user/boar_detection.service"

  # ② 生成 start.sh（不依赖 systemd：开机自启/自愈/立即启动 都调它）
  #    自愈策略：健康→不动；启动中(<90s)→等；进程死→拉起；卡死(>90s仍无响应)→强杀重启
  cat > "$DEPLOY_DIR/start.sh" <<EOF
#!/bin/bash
# 野猪检测服务 保健康脚本（用户级，不依赖 systemd）
cd "$DEPLOY_DIR"
export LD_LIBRARY_PATH="$MINICONDA_DIR/envs/boar/lib"
PIDFILE="$DEPLOY_DIR/service.pid"
URL="http://127.0.0.1:5000/health"

# ① 健康 → 不动
if curl -sf -m 3 "\$URL" >/dev/null 2>&1; then
  exit 0
fi

# ② 读 pidfile；进程真活着？(/proc 存在且 cmdline 非空=非僵尸)
pid=""
[ -f "\$PIDFILE" ] && pid="\$(cat "\$PIDFILE" 2>/dev/null)"
proc_alive=0
age=9999
if [ -n "\$pid" ] && [ -d "/proc/\$pid" ] && [ -s "/proc/\$pid/cmdline" ]; then
  proc_alive=1
  age=\$(( \$(date +%s) - \$(stat -c %Y "/proc/\$pid" 2>/dev/null || echo 0) ))
fi

# ③ 刚启动不足 90 秒 → 正在加载模型，等它，不干预
if [ "\$proc_alive" = "1" ] && [ "\$age" -lt 90 ]; then
  exit 0
fi

# ④ 进程活着但超 90 秒仍无响应 → 判定卡死，强杀重启
if [ "\$proc_alive" = "1" ]; then
  echo "[$(date '+%F %T')] 进程卡死(\${age}s无响应)，强制重启" >> "$DEPLOY_DIR/service.log"
  kill "\$pid" 2>/dev/null || true
  sleep 3
fi

# ⑤ 兜底清理残留进程（防 pidfile 丢失但进程还在）
pkill -f "boar-detection/app.py" 2>/dev/null || true
sleep 1

# ⑥ 启动
nohup "$PY" "$DEPLOY_DIR/app.py" >> "$DEPLOY_DIR/service.log" 2>&1 &
echo \$! > "\$PIDFILE"
exit 0
EOF
  chmod +x "$DEPLOY_DIR/start.sh"

  # ③ 桌面开机自启（登录桌面即自动启动，100% 可靠）
  mkdir -p "$HOME/.config/autostart"
  cat > "$HOME/.config/autostart/boar_detection.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=野猪检测服务
Comment=开机自动启动野猪检测服务
Exec=bash $DEPLOY_DIR/start.sh
X-GNOME-Autostart-enabled=true
Hidden=false
Terminal=false
EOF

  # ④ systemd --user 尽力尝试（静默，失败不影响）
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  if systemctl --user daemon-reload >/dev/null 2>&1 && systemctl --user enable --now boar_detection >/dev/null 2>&1; then
    echo "  ✅ systemd 用户级自启已启用 / systemd user auto-start enabled"
  else
    echo "  ℹ️ systemd 用户级不可用，已用开机自启代替（不影响使用）/ using desktop auto-start instead"
  fi
  loginctl enable-linger "$(id -un)" 2>/dev/null || true

  # ⑤ 立即启动（不管 systemd 是否可用，现在就跑起来）
  bash "$DEPLOY_DIR/start.sh"
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
    # 修正桌面图标 Exec 指向部署目录（模板默认写的是 /opt/boar-detection）
    if [ -f "$DEPLOY_DIR/boar_diag.desktop" ]; then
      sed "s|bash /opt/boar-detection/boar_diag.sh|bash $DEPLOY_DIR/boar_diag.sh|" \
          "$DEPLOY_DIR/boar_diag.desktop" > "$HOME/Desktop/boar_diag.desktop" 2>/dev/null
      chmod +x "$HOME/Desktop/boar_diag.desktop" 2>/dev/null || true
    fi
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
  # 用户模式：健康探活用用户 crontab，日志写 home，重启调 start.sh（不依赖 systemd）
  if [ -f "$DEPLOY_DIR/start.sh" ]; then
    # 生成用户健康脚本：/health 无响应就调 start.sh 自愈
    cat > "$DEPLOY_DIR/boar_health_user.sh" <<EOF
#!/bin/bash
# 野猪检测服务 自愈探活（用户级，不依赖 systemd）
URL="http://127.0.0.1:5000/health"
LOG="$DEPLOY_DIR/boar_health.log"
if ! curl -sf -m 5 "\$URL" >/dev/null 2>&1; then
  echo "\$(date '+%F %T') /health 无响应，调用 start.sh 重启" >> "\$LOG" 2>/dev/null || true
  bash "$DEPLOY_DIR/start.sh" >> "\$LOG" 2>&1 || true
fi
EOF
    chmod +x "$DEPLOY_DIR/boar_health_user.sh"
    # 加入用户 crontab
    ( crontab -l 2>/dev/null | grep -v "boar_health\|boar_detect_" ; \
      echo "* * * * * bash $DEPLOY_DIR/boar_health_user.sh" ; \
      echo "*/30 * * * * find /tmp -maxdepth 1 -name 'boar_detect_*.mp4' -mmin +10 -delete" ) | crontab -
    # 校验自愈探活是否真的装上（cron 缺失则提示，服务挂了不会自动恢复）
    if crontab -l 2>/dev/null | grep -q "boar_health_user"; then
      echo "  ✅ 自愈探活已装（每 1 分钟检查，挂了自动拉起）/ self-heal active (check every 1 min)"
    else
      echo "  ⚠️ 未能添加自愈探活 cron，服务异常时不会自动恢复"
      echo "  ⚠️ Self-heal cron NOT installed - service won't auto-recover"
    fi
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
  echo " ⚠️ 服务未能就绪，自动运行完整诊断工具（结果直接显示在下面）"
  echo " ⚠️ Service not ready, running full diagnostic below..."
  if [ -f "$DEPLOY_DIR/boar_diag.sh" ]; then
    bash "$DEPLOY_DIR/boar_diag.sh"
  fi
  echo " （完整报告也存到了 /tmp/boar_diag_report.txt）"
  echo " （Full report saved to /tmp/boar_diag_report.txt）"
  echo "======================================================"
fi
echo "[$(date '+%F %T')] ===== 安装结束 / Install finished ====="
echo "  安装+检查日志已保存到 / Log saved to: $LOG_FILE"
echo "  请把 U盘 上这个 install_log.txt 文件发给技术人员（或直接拍照/发文件）"
echo "  Please send the install_log.txt on the USB to tech support"
echo ""
echo "按回车键关闭窗口 / Press Enter to close"
read _
