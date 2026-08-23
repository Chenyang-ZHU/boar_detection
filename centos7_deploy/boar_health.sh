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
# ============================================================
set -u

URL="http://127.0.0.1:5000/health"
SERVICE="boar_detection"
LOG="/var/log/boar_health.log"

# 探测健康：5 秒内无响应视为异常
if ! curl -sf -m 5 "$URL" >/dev/null 2>&1; then
  # 仅当服务处于 active 状态才重启（避免重启被手动停止的服务）
  if systemctl is-active --quiet "$SERVICE"; then
    echo "$(date '+%F %T') 健康检查失败（超时/无响应），重启 $SERVICE" >> "$LOG"
    systemctl restart "$SERVICE"
  else
    echo "$(date '+%F %T') 健康检查失败，但 $SERVICE 非 active，不干预" >> "$LOG"
  fi
fi
