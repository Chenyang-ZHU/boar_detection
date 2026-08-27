#!/bin/bash
# ============================================================
# CentOS 7 野猪检测服务 一键部署脚本
#
# 用法: 在 centos7_deploy/ 目录下执行
#     sudo bash install_centos7.sh
#
# 前提:
#   - CentOS 7 (glibc 2.17)
#   - 需要 root / sudo
#   - 有网络（下载 Miniconda + 依赖）
#
# 脚本会自动:
#   1. 安装 Miniconda（提供 Python 3.10）
#   2. 用 conda-forge 装编译型依赖（保证 glibc 2.17 兼容）
#   3. 用 pip 装 torch 2.6.0 CPU 版（glibc 2.17 兼容的最高版）
#   4. 部署服务代码 + 模型到 /opt/boar-detection
#   5. 配置 systemd 开机自启
# ============================================================
set -euo pipefail

# ---------- 配置 ----------
DEPLOY_DIR="/opt/boar-detection"
ENV_NAME="boar"
PYTHON_VER="3.10"
MINICONDA_DIR="/opt/miniconda3"
# ⚠️ 不要改回 latest：Miniconda 自 24.x 起要求 glibc >= 2.28，CentOS 7 (glibc 2.17) 装不上，
#    报 "Installer requires GLIBC >=2.28, but system has 2.17"。钉死 23.10.0-1（2023 年构建，支持 glibc 2.17）。
MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-py311_23.10.0-1-Linux-x86_64.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_SRC="$REPO_ROOT/work/service"
MODEL_SRC="$REPO_ROOT/work/runs/detect/boar_detection/yolov8n_merged_final/weights/best.pt"

# ---------- 检查 ----------
if [ "$(id -u)" -ne 0 ]; then
  echo "❌ 请用 root 运行: sudo bash install_centos7.sh"
  exit 1
fi
if [ ! -f "$MODEL_SRC" ]; then
  echo "❌ 找不到模型文件: $MODEL_SRC"
  echo "   请确认在仓库根目录的 centos7_deploy/ 下运行本脚本"
  exit 1
fi

log() { echo ""; echo "===== $1 ====="; }

# ---------- [1/7] Miniconda ----------
log "[1/7] 安装 Miniconda (Python 3.10 环境)"
if [ ! -x "$MINICONDA_DIR/bin/conda" ]; then
  echo "下载 Miniconda..."
  wget -q "$MINICONDA_URL" -O /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b -p "$MINICONDA_DIR"
  echo "✅ Miniconda 已安装到 $MINICONDA_DIR"
else
  echo "✅ Miniconda 已存在"
fi
export PATH="$MINICONDA_DIR/bin:$PATH"

# ---------- [2/7] 创建 conda 环境 ----------
log "[2/7] 创建 Python $PYTHON_VER 环境 $ENV_NAME"
if ! conda env list | grep -qE "^\s*$ENV_NAME\s"; then
  conda create -y -n "$ENV_NAME" "python=$PYTHON_VER" -c conda-forge
  echo "✅ 环境 $ENV_NAME 已创建"
else
  echo "✅ 环境 $ENV_NAME 已存在"
fi
PY="$MINICONDA_DIR/envs/$ENV_NAME/bin/python"
PIP="$MINICONDA_DIR/envs/$ENV_NAME/bin/pip"
# conda 环境的库目录：CentOS 7 系统 libstdc++ 太老（最高 GLIBCXX_3.4.19），
# 必须让服务用 conda 的 libstdc++（否则 PIL 报 "GLIBCXX_3.4.21 not found"）
CONDA_LIB="$MINICONDA_DIR/envs/$ENV_NAME/lib"

# ---------- [3/7] conda-forge 编译型依赖 ----------
log "[3/7] conda-forge 安装编译型依赖（glibc 2.17 兼容）"
conda install -y -n "$ENV_NAME" -c conda-forge \
  "numpy=1.26" opencv scipy pandas "matplotlib=3.7" \
  pillow pyyaml tqdm requests psutil seaborn
echo "✅ conda 依赖装好"

# ---------- [4/7] torch CPU 版 ----------
log "[4/7] pip 安装 torch 2.6.0 CPU 版 + torchvision 0.21.0"
"$PIP" install "torch==2.6.0" "torchvision==0.21.0" \
  --index-url https://download.pytorch.org/whl/cpu
echo "✅ torch CPU 版装好"

# ---------- [5/8] ultralytics + flask + waitress ----------
# ultralytics 用 --no-deps（复用 conda 的 cv2/numpy，避免 pip 拉到不兼容的编译版）；
# flask/waitress 单独装、不带 --no-deps，否则缺 werkzeug/jinja2 等依赖，服务启动即报 ModuleNotFoundError。
log "[5/8] 安装 ultralytics + flask + waitress"
"$PIP" install --no-deps ultralytics==8.4.114 py-cpuinfo ultralytics-thop
"$PIP" install "flask>=3.0"
"$PIP" install "waitress==3.0.2"
echo "✅ ultralytics + flask + waitress 装好"

# ---------- [6/7] 部署服务文件 ----------
log "[6/7] 部署服务文件到 $DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"
cp "$SERVICE_SRC/app.py" "$SERVICE_SRC/detector.py" "$DEPLOY_DIR/"
cp "$MODEL_SRC" "$DEPLOY_DIR/best.pt"
cp "$SCRIPT_DIR/config.centos7.py" "$DEPLOY_DIR/config.py"
# 同时把 systemd 单元也放进部署目录（带 @PY@/@DEPLOY_DIR@/@CONDA_LIB@ 占位符），
# 供离线打包（deploy_offline.sh 会从 /opt/boar-detection/boar_detection.service 读取并替换）
cp "$SCRIPT_DIR/boar_detection.service" "$DEPLOY_DIR/"
ls -la "$DEPLOY_DIR/"
echo "✅ 服务文件已部署"

# ---------- [7/8] systemd ----------
log "[7/8] 安装 systemd 开机自启"
cp "$SCRIPT_DIR/boar_detection.service" /etc/systemd/system/
sed -i "s|@PY@|$PY|g" /etc/systemd/system/boar_detection.service
sed -i "s|@DEPLOY_DIR@|$DEPLOY_DIR|g" /etc/systemd/system/boar_detection.service
sed -i "s|@CONDA_LIB@|$CONDA_LIB|g" /etc/systemd/system/boar_detection.service
systemctl daemon-reload
systemctl enable --now boar_detection

# ---------- [8/8] 健壮性加固 ----------
log "[8/8] 健壮性加固（探活自愈 + 日志限容 + 临时文件清理）"
# 健康探活脚本 + cron（覆盖"进程活着但卡死"，systemd Restart 只管崩溃）
mkdir -p /etc/cron.d
cp "$SCRIPT_DIR/boar_health.sh" /usr/local/bin/boar_health.sh
cp "$SCRIPT_DIR/boar_health.sh" "$DEPLOY_DIR/boar_health.sh"   # 放进部署目录供离线打包
chmod +x /usr/local/bin/boar_health.sh
chmod +x "$DEPLOY_DIR/boar_health.sh"
# 一键诊断脚本（甲方可直接运行，输出排查报告）
cp "$SCRIPT_DIR/boar_diag.sh" "$DEPLOY_DIR/boar_diag.sh"
chmod +x "$DEPLOY_DIR/boar_diag.sh"
cat > /etc/cron.d/boar_health << 'EOF'
* * * * * root /usr/local/bin/boar_health.sh
EOF
chmod 644 /etc/cron.d/boar_health
# 视频临时文件清理（每 30 分钟清一次超过 10 分钟的残留，防进程被杀后堆积）
cat > /etc/cron.d/boar_tmp_clean << 'EOF'
*/30 * * * * root find /tmp -maxdepth 1 -name 'boar_detect_*.mp4' -mmin +10 -delete
EOF
chmod 644 /etc/cron.d/boar_tmp_clean
# journald 日志限容（500M，防长跑撑爆分区）
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/boar.conf
systemctl restart systemd-journald 2>/dev/null || true
echo "✅ 加固完成：探活 cron / 临时文件清理 / journald 500M"

# ---------- 验证 ----------
log "验证"
echo "--- systemd 状态 ---"
systemctl status boar_detection --no-pager | head -6
echo ""
echo "--- 健康检查（最多等 40s：服务冷启动需加载模型，8s 固定 sleep 不够）---"
ready=""
for i in 1 2 3 4 5 6 7 8; do
  if curl -s -m 3 http://127.0.0.1:5000/health; then
    echo ""
    ready="yes"
    break
  fi
  sleep 5
done
[ -n "$ready" ] || echo "(服务尚未就绪，稍后可再执行: curl http://127.0.0.1:5000/health)"

echo ""
echo "=========================================="
echo " ✅ 部署完成！"
echo " 局域网地址: http://<本机IP>:5000"
echo " 测试命令:"
echo "   curl http://<本机IP>:5000/health"
echo "   curl -X POST http://<本机IP>:5000/detect -F 'image=@test.jpg'"
echo "=========================================="
