#!/bin/bash
# ============================================================
# 野猪检测服务 健康探活脚本（配合 cron 每 1 分钟执行一次）
#
# 作用：
#   服务进程崩溃 → systemd Restart=always 处理（本脚本不干预）
#   "进程活着但无响应"（卡死/线程耗尽）→ systemd 不处理，
#   本脚本探测 /health 超时则强制重启，实现自愈。
#
# 用法（由 cron 调用）：
#   * * * * * root /usr/local/bin/boar_health.sh
#
# 兼容性：CentOS 7 与 Jetson 通用（curl / python3 / python / /dev/tcp 任选可用者）
# ============================================================
set -u

URL="http://127.0.0.1:5000/health"
SERVICE="boar_detection"
# 系统级安装为空；用户级安装时 install 脚本会改写为 "--user"
SCOPE=""
LOG="/var/log/boar_health.log"

# 通用健康检查函数（按可用工具降级）
if command -v curl >/dev/null 2>&1; then
  check() { curl -sf -m 5 "$URL" >/dev/null 2>&1; }
elif command -v python3 >/dev/null 2>&1; then
  check() { python3 -c "import urllib.request; urllib.request.urlopen('$URL', timeout=5)" >/dev/null 2>&1; }
elif command -v python >/dev/null 2>&1; then
  check() { python -c "import urllib.request; urllib.request.urlopen('$URL', timeout=5)" >/dev/null 2>&1; }
else
  # 兜底：仅探测端口可达（无法验证应用响应，但聊胜于无）
  check() { timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/5000" 2>/dev/null; }
fi

# 用户级安装需 XDG_RUNTIME_DIR 才能连用户会话总线（cron 环境默认没有）
[ -z "${XDG_RUNTIME_DIR:-}" ] && export XDG_RUNTIME_DIR="/run/user/$(id -u)"

# 探测健康：5 秒内无响应视为异常
if ! check; then
  # 仅当服务处于 active 状态才重启（避免重启被手动停止的服务）
  if systemctl $SCOPE is-active --quiet "$SERVICE"; then
    echo "$(date '+%F %T') 健康检查失败（超时/无响应），重启 $SERVICE" >> "$LOG" 2>/dev/null || true
    systemctl $SCOPE restart "$SERVICE"
  else
    echo "$(date '+%F %T') 健康检查失败，但 $SERVICE 非 active，不干预" >> "$LOG" 2>/dev/null || true
  fi
fi
