#!/bin/bash
# ============================================================
# 野猪检测服务 · 一键诊断脚本（给无计算机基础的甲方用）
#
# 用法（一条命令）:
#     sudo bash boar_diag.sh
#
# 输出:
#     1. 屏幕直接显示 ✅/❌ 结果（绿=正常 红=有问题）
#     2. 完整报告存到 /tmp/boar_diag_report.txt，可发给技术人员
#
# 说明: 只读诊断，不做任何修改，可放心运行。
# ============================================================
set -u

REPORT="/tmp/boar_diag_report.txt"
: > "$REPORT"

# 同时输出到屏幕和报告文件
out() { echo "$@" | tee -a "$REPORT"; }

# 自动探测部署路径和 python
DEPLOY=""
if [ -d /opt/boar-detection ]; then DEPLOY=/opt/boar-detection; fi
if [ -d /home/nvidia/boar-detection ]; then DEPLOY=/home/nvidia/boar-detection; fi

PY=""
for p in /opt/miniconda3/envs/boar/bin/python /home/nvidia/boar-detection/venv/bin/python python3; do
  command -v "$p" >/dev/null 2>&1 && PY="$p" && break
done

URL="http://127.0.0.1:5000"

echo "======================================================" | tee -a "$REPORT"
echo "  野猪检测服务 · 一键诊断报告" | tee -a "$REPORT"
echo "  生成时间: $(date '+%F %T')" | tee -a "$REPORT"
echo "======================================================" | tee -a "$REPORT"

# ---------- 1. 服务状态 ----------
out ""
out "===== 1. 服务状态 ====="
if command -v systemctl >/dev/null 2>&1; then
  ACTIVE=$(systemctl is-active boar_detection 2>/dev/null)
  if [ "$ACTIVE" = "active" ]; then
    out "  ✅ 服务运行中 (active)"
  else
    out "  ❌ 服务未运行 ($ACTIVE)"
  fi
  out "  重启次数: $(systemctl show boar_detection -p NRestarts --value 2>/dev/null)"
  out "  最近启动: $(systemctl show boar_detection -p ActiveEnterTimestamp --value 2>/dev/null)"
else
  out "  ⚠️ 无法读取 systemctl（容器或无 systemd 环境）"
fi

# ---------- 2. 健康检查 ----------
out ""
out "===== 2. 健康检查 (/health) ====="
if [ -n "$PY" ]; then
  HEALTH=$($PY -c "import urllib.request,json; d=json.load(urllib.request.urlopen('$URL/health',timeout=5)); print(d.get('status'), d.get('device'), d.get('model_loaded'))" 2>&1)
  STATUS=$(echo "$HEALTH" | awk '{print $1}')
  if [ "$STATUS" = "ok" ]; then
    out "  ✅ /health 正常: $HEALTH"
  else
    out "  ❌ /health 异常: $HEALTH"
    out "  （服务可能没起来，看下面的日志）"
  fi
else
  out "  ❌ 找不到 python，无法检查接口"
fi

# ---------- 3. 服务日志（最近报错） ----------
out ""
out "===== 3. 服务日志（最近 15 行错误） ====="
if command -v journalctl >/dev/null 2>&1; then
  ERR=$(journalctl -u boar_detection --no-pager -n 100 2>/dev/null | grep -iE "error|Traceback|Exception|Failed|Killed" | tail -5)
  if [ -n "$ERR" ]; then
    out "  ⚠️ 发现以下错误:"
    echo "$ERR" | tee -a "$REPORT"
  else
    out "  ✅ 最近日志无错误"
  fi
else
  out "  ⚠️ 无 journalctl"
fi

# ---------- 4. 依赖检查 ----------
out ""
out "===== 4. 依赖检查 ====="
if [ -n "$PY" ]; then
  MISSING=0
  for mod in flask waitress qtfaststart imageio_ffmpeg torch ultralytics cv2; do
    if $PY -c "import $mod" >/dev/null 2>&1; then
      out "  ✅ $mod"
    else
      out "  ❌ $mod (缺失!)"
      MISSING=1
    fi
  done
  [ $MISSING -eq 0 ] && out "  → 依赖齐全"
else
  out "  ❌ 找不到 python"
fi

# ---------- 5. 模型文件 ----------
out ""
out "===== 5. 模型文件 ====="
if [ -n "$DEPLOY" ]; then
  if [ -f "$DEPLOY/best.pt" ]; then
    SIZE=$(stat -c%s "$DEPLOY/best.pt" 2>/dev/null)
    if [ "$SIZE" -gt 1000000 ]; then
      out "  ✅ 模型存在 ($DEPLOY/best.pt, $SIZE bytes)"
    else
      out "  ❌ 模型文件异常小 ($SIZE bytes)，可能损坏"
    fi
  else
    out "  ❌ 模型文件不存在: $DEPLOY/best.pt"
  fi
else
  out "  ❌ 找不到部署目录"
fi

# ---------- 6. 系统环境已知坑 ----------
out ""
out "===== 6. 系统环境检查 ====="
# /dev/null
if [ -c /dev/null ]; then
  out "  ✅ /dev/null 正常 (字符设备)"
else
  out "  ❌ /dev/null 异常! 修复: sudo rm /dev/null && sudo mknod -m 666 /dev/null c 1 3"
fi
# libstdc++
GLIBCXX=$($PY -c "import ctypes; lib=ctypes.CDLL('libstdc++.so.6'); print('ok')" 2>&1 | tail -1)
if [ "$GLIBCXX" = "ok" ]; then
  out "  ✅ libstdc++ 可加载"
else
  out "  ❌ libstdc++ 异常: $GLIBCXX"
fi
# 内存/磁盘
MEM=$(free -h 2>/dev/null | awk 'NR==2{print $2" 总量, "$4" 可用"}')
out "  内存: $MEM"
DISK=$(df -h / 2>/dev/null | awk 'NR==2{print $3" 已用 / "$2" 总量 ("$5")"}')
out "  磁盘: $DISK"

# ---------- 7. 接口快速测试 ----------
out ""
out "===== 7. 接口测试 ====="
if [ -n "$PY" ] && [ -n "$DEPLOY" ]; then
  TEST=$($PY - << PYEOF 2>&1
import urllib.request, json
try:
    d = json.load(urllib.request.urlopen("$URL/health", timeout=5))
    print("HEALTH_OK")
except Exception as e:
    print("HEALTH_FAIL", e)
PYEOF
)
  out "  $TEST"
else
  out "  ⚠️ 跳过接口测试（缺 python 或部署目录）"
fi

# ---------- 8. 视频编码检查（H.264 + moov 前置） ----------
out ""
out "===== 8. 视频编码检查 ====="
if [ -n "$PY" ] && [ -f "$DEPLOY/best.pt" ]; then
  VCHECK=$($PY - << PYEOF 2>&1
import urllib.request, json, struct, io, time, os, cv2
BASE = "$URL"

def multipart(field, filename, data, ctype):
    boundary = "----boardiag"
    body = ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
            "Content-Type: %s\r\n\r\n" % (boundary, field, filename, ctype)).encode() + data
    body += ("\r\n--%s--\r\n" % boundary).encode()
    return body, "multipart/form-data; boundary=%s" % boundary

try:
    # 用 numpy 生成纯色帧，写一个 5 帧测试视频
    import numpy as np
    frame = np.full((640, 640, 3), 128, dtype=np.uint8)
    # 写一个 5 帧测试视频
    tmpv = "/tmp/boardiag.mp4"
    w = cv2.VideoWriter(tmpv, cv2.VideoWriter_fourcc(*"mp4v"), 5, (640, 640))
    for _ in range(5):
        w.write(frame)
    w.release()
    vdata = open(tmpv, "rb").read()
    os.remove(tmpv)

    # 调 /detect/video
    body, ct = multipart("video", "t.mp4", vdata, "video/mp4")
    req = urllib.request.Request(BASE + "/detect/video", data=body, headers={"Content-Type": ct})
    resp = urllib.request.urlopen(req, timeout=60)
    vb = resp.read()
    h = resp.headers

    # 编码检查
    avcc = vb.count(b"avcC")
    mp4v = vb.count(b"mp4v")
    # moov 位置（在 mdat 之前 = 前置）
    pos, ats = 0, []
    while pos < len(vb) and len(ats) < 6:
        if pos + 8 > len(vb): break
        s, t = struct.unpack(">I4s", vb[pos:pos+8])
        if s == 0: break
        ats.append(t.decode("latin1")); pos += s
    moov_front = "moov" in ats and ats.index("moov") < ats.index("mdat") if "mdat" in ats else "moov" in ats[:2]

    boar_count = h.get("X-Boar-Count", "?")
    print("VIDEO_OK size=%dB H264(avcC)=%s mp4v=%s atom=%s moov前置=%s X-Boar-Count=%s" % (
        len(vb), avcc, mp4v, "->".join(ats[:4]), "OK" if moov_front else "FAIL", boar_count))
    if avcc == 0 or not moov_front:
        print("  ⚠️ 编码不是 H.264 或 moov 未前置 → 浏览器可能无法播放，需技术人员处理")
except Exception as e:
    print("VIDEO_FAIL", e)
PYEOF
)
  echo "$VCHECK" | tee -a "$REPORT"
else
  out "  ⚠️ 跳过视频编码检查"
fi

# ---------- 总结 ----------
out ""
out "======================================================"
PASS=$(grep -c "✅" "$REPORT" 2>/dev/null)
FAIL=$(grep -c "❌" "$REPORT" 2>/dev/null)
out " 检查结果: $PASS 项正常, $FAIL 项异常"
if [ "${FAIL:-0}" -gt 0 ]; then
  out " ⚠️ 有异常项，请把下面报告发给技术人员处理"
else
  out " ✅ 所有检查通过，服务正常"
fi
out " 报告已保存: $REPORT"
out "======================================================"
