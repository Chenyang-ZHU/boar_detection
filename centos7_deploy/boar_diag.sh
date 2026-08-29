#!/bin/bash
# ============================================================
# 野猪检测服务 · 一键诊断脚本（给无计算机基础的甲方用）
# Boar Detection Service - One-click Diagnostic (for non-technical users)
#
# 用法（一条命令）/ Usage (one command):
#     sudo bash boar_diag.sh
#
# 输出 / Output:
#     1. 屏幕直接显示 ✅/❌ 结果 / Results shown on screen (✅=OK ❌=problem)
#     2. 完整报告存到 /tmp/boar_diag_report.txt，可发给技术人员
#        Full report saved to /tmp/boar_diag_report.txt for technical support
#
# 说明: 只读诊断，不做任何修改，可放心运行。
# Note: Read-only diagnostic, makes no changes, safe to run.
# ============================================================
set -u

REPORT="/tmp/boar_diag_report.txt"
: > "$REPORT"

# 同时输出到屏幕和报告文件 / Output to screen + report file
out() { echo "$@" | tee -a "$REPORT"; }

# 自动探测部署路径和 python / Auto-detect deploy path and python
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
echo "  Boar Detection Service - Diagnostic Report" | tee -a "$REPORT"
echo "  生成时间 / Time: $(date '+%F %T')" | tee -a "$REPORT"
echo "======================================================" | tee -a "$REPORT"

# ---------- 1. 服务状态 / Service status ----------
out ""
out "===== 1. 服务状态 / Service Status ====="
if command -v systemctl >/dev/null 2>&1; then
  ACTIVE=$(systemctl is-active boar_detection 2>/dev/null)
  if [ "$ACTIVE" = "active" ]; then
    out "  ✅ 服务运行中 (active) / Service running"
  else
    out "  ❌ 服务未运行 ($ACTIVE) / Service not running"
  fi
  out "  重启次数 / Restarts: $(systemctl show boar_detection -p NRestarts --value 2>/dev/null)"
  out "  最近启动 / Started: $(systemctl show boar_detection -p ActiveEnterTimestamp --value 2>/dev/null)"
else
  out "  ⚠️ 无法读取 systemctl（容器或无 systemd 环境）/ Cannot read systemctl (container or no systemd)"
fi

# ---------- 2. 健康检查 / Health check ----------
out ""
out "===== 2. 健康检查 (/health) / Health Check ====="
if [ -n "$PY" ]; then
  HEALTH=$($PY -c "import urllib.request,json; d=json.load(urllib.request.urlopen('$URL/health',timeout=5)); print(d.get('status'), d.get('device'), d.get('model_loaded'))" 2>&1)
  STATUS=$(echo "$HEALTH" | awk '{print $1}')
  if [ "$STATUS" = "ok" ]; then
    out "  ✅ /health 正常: $HEALTH / Health OK"
  else
    out "  ❌ /health 异常: $HEALTH / Health FAILED"
    out "  （服务可能没起来，看下面的日志）/ Service may not be up, check logs below"
  fi
else
  out "  ❌ 找不到 python，无法检查接口 / No python found, cannot check API"
fi

# ---------- 3. 服务日志（最近报错）/ Service log (recent errors) ----------
out ""
out "===== 3. 服务日志（最近错误）/ Service Log (recent errors) ====="
if command -v journalctl >/dev/null 2>&1; then
  ERR=$(journalctl -u boar_detection --no-pager -n 100 2>/dev/null | grep -iE "error|Traceback|Exception|Failed|Killed" | tail -5)
  if [ -n "$ERR" ]; then
    out "  ⚠️ 发现以下错误 / Errors found:"
    echo "$ERR" | tee -a "$REPORT"
  else
    out "  ✅ 最近日志无错误 / No errors in recent logs"
  fi
else
  out "  ⚠️ 无 journalctl / No journalctl available"
fi

# ---------- 4. 依赖检查 / Dependency check ----------
out ""
out "===== 4. 依赖检查 / Dependencies ====="
if [ -n "$PY" ]; then
  MISSING=0
  for mod in flask waitress qtfaststart imageio_ffmpeg torch ultralytics cv2; do
    if $PY -c "import $mod" >/dev/null 2>&1; then
      out "  ✅ $mod"
    else
      out "  ❌ $mod (缺失! / MISSING!)"
      MISSING=1
    fi
  done
  [ $MISSING -eq 0 ] && out "  → 依赖齐全 / All dependencies OK"
else
  out "  ❌ 找不到 python / No python found"
fi

# ---------- 5. 模型文件 / Model file ----------
out ""
out "===== 5. 模型文件 / Model File ====="
if [ -n "$DEPLOY" ]; then
  if [ -f "$DEPLOY/best.pt" ]; then
    SIZE=$(stat -c%s "$DEPLOY/best.pt" 2>/dev/null)
    if [ "$SIZE" -gt 1000000 ]; then
      out "  ✅ 模型存在 ($DEPLOY/best.pt, $SIZE bytes) / Model OK"
    else
      out "  ❌ 模型文件异常小 ($SIZE bytes)，可能损坏 / Model suspiciously small, may be corrupt"
    fi
  else
    out "  ❌ 模型文件不存在 / Model not found: $DEPLOY/best.pt"
  fi
else
  out "  ❌ 找不到部署目录 / Deploy directory not found"
fi

# ---------- 6. 系统环境已知坑 / System environment checks ----------
out ""
out "===== 6. 系统环境检查 / System Environment ====="
# /dev/null
if [ -c /dev/null ]; then
  out "  ✅ /dev/null 正常 (字符设备) / /dev/null OK (char device)"
else
  out "  ❌ /dev/null 异常! 修复 / Broken! Fix: sudo rm /dev/null && sudo mknod -m 666 /dev/null c 1 3"
fi
# libstdc++
GLIBCXX=$($PY -c "import ctypes; lib=ctypes.CDLL('libstdc++.so.6'); print('ok')" 2>&1 | tail -1)
if [ "$GLIBCXX" = "ok" ]; then
  out "  ✅ libstdc++ 可加载 / libstdc++ OK"
else
  out "  ❌ libstdc++ 异常: $GLIBCXX / libstdc++ issue"
fi
# 内存/磁盘 / Memory / Disk
MEM=$(free -h 2>/dev/null | awk 'NR==2{print $2" total, "$4" free"}')
out "  内存 / Memory: $MEM"
DISK=$(df -h / 2>/dev/null | awk 'NR==2{print $3" used / "$2" total ("$5")"}')
out "  磁盘 / Disk: $DISK"

# ---------- 7. 接口快速测试 / API quick test ----------
out ""
out "===== 7. 接口测试 / API Test ====="
if [ -n "$PY" ] && [ -n "$DEPLOY" ]; then
  TEST=$($PY - << PYEOF 2>&1
import urllib.request, json
try:
    d = json.load(urllib.request.urlopen("$URL/health", timeout=5))
    print("API_OK")
except Exception as e:
    print("API_FAIL", e)
PYEOF
)
  out "  $TEST"
else
  out "  ⚠️ 跳过接口测试（缺 python 或部署目录）/ Skipped API test (no python or deploy dir)"
fi

# ---------- 8. 视频编码检查 / Video codec check ----------
out ""
out "===== 8. 视频编码检查 / Video Codec Check ====="
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
    # 用 numpy 生成纯色帧，写一个 5 帧测试视频 / Generate a 5-frame test video
    import numpy as np
    frame = np.full((640, 640, 3), 128, dtype=np.uint8)
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

    # 编码检查 / Codec check
    avcc = vb.count(b"avcC")
    mp4v = vb.count(b"mp4v")
    # moov 位置 / moov position
    pos, ats = 0, []
    while pos < len(vb) and len(ats) < 6:
        if pos + 8 > len(vb): break
        s, t = struct.unpack(">I4s", vb[pos:pos+8])
        if s == 0: break
        ats.append(t.decode("latin1")); pos += s
    moov_front = "moov" in ats and ats.index("moov") < ats.index("mdat") if "mdat" in ats else "moov" in ats[:2]

    boar_count = h.get("X-Boar-Count", "?")
    print("VIDEO_OK size=%dB H264(avcC)=%s mp4v=%s atom=%s moov_front=%s X-Boar-Count=%s" % (
        len(vb), avcc, mp4v, "->".join(ats[:4]), "OK" if moov_front else "FAIL", boar_count))
    if avcc == 0 or not moov_front:
        print("  WARNING: not H.264 or moov not at front - browser may not play, contact support")
except Exception as e:
    print("VIDEO_FAIL", e)
PYEOF
)
  echo "$VCHECK" | tee -a "$REPORT"
else
  out "  ⚠️ 跳过视频编码检查 / Skipped video codec check"
fi

# ---------- 总结 / Summary ----------
out ""
out "======================================================"
PASS=$(grep -c "✅" "$REPORT" 2>/dev/null)
FAIL=$(grep -c "❌" "$REPORT" 2>/dev/null)
out " 检查结果: $PASS 项正常, $FAIL 项异常 / Result: $PASS OK, $FAIL issues"
if [ "${FAIL:-0}" -gt 0 ]; then
  out " ⚠️ 有异常项，请把下面报告发给技术人员处理 / Issues found, send report to technical support"
else
  out " ✅ 所有检查通过，服务正常 / All checks passed, service OK"
fi
out " 报告已保存 / Report saved: $REPORT"
out "======================================================"
