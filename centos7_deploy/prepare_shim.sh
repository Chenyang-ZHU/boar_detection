#!/bin/bash
# ============================================================
# 容器内准备 systemctl shim（本地 Docker 验证离线部署用）
#
# 容器里没有 systemd，而 deploy_offline.sh 用 systemctl 启动服务。
# 本脚本在容器内生成 /usr/local/sbin/systemctl 来模拟 systemd：
#   - daemon-reload / status: 模拟成功
#   - enable: 解析 unit 的 ExecStart / WorkingDirectory / Environment（含 LD_LIBRARY_PATH），
#             用 nohup 真实拉起服务进程
#
# 用法（进入容器后执行）:
#     bash /bundle/prepare_shim.sh
# ============================================================
set -euo pipefail

cat > /usr/local/sbin/systemctl <<'SHIM_EOF'
#!/bin/bash
cmd="${1:-}"
case "$cmd" in
  daemon-reload) exit 0 ;;
  enable)
    unit="/etc/systemd/system/boar_detection.service"
    [ -f "$unit" ] || { echo "shim: unit 不存在"; exit 1; }
    exe="$(grep -E '^ExecStart=' "$unit" | head -1 | sed 's/^ExecStart=//' | xargs)"
    wd="$(grep -E '^WorkingDirectory=' "$unit" | head -1 | sed 's/^WorkingDirectory=//' | xargs)"
    envs=""
    while IFS= read -r line; do [ -n "$line" ] && envs="$envs $line"; done < <(grep -E '^Environment=' "$unit" | sed 's/^Environment=//')
    [ -n "$exe" ] || { echo "shim: 未找到 ExecStart"; exit 1; }
    mkdir -p "${wd:-/}"; cd "${wd:-/}" || exit 1
    # shellcheck disable=SC2086
    env $envs nohup $exe >>/var/log/boar_detection.log 2>&1 &
    disown 2>/dev/null || true
    echo "shim: 已启动 -> $exe"
    exit 0
    ;;
  status) echo "● active (shim)"; exit 0 ;;
  *) echo "shim no-op: $*"; exit 0 ;;
esac
SHIM_EOF
chmod +x /usr/local/sbin/systemctl
echo "✅ systemctl shim 已就绪: /usr/local/sbin/systemctl"
