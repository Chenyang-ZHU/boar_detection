"""通过 ngrok 将本地服务暴露到公网"""
import time
import sys
import os
import subprocess
from pyngrok import ngrok, conf

# 确保在 service 目录下运行
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 先启动 Flask 服务（后台）
print("正在启动野猪检测服务...")
server = subprocess.Popen(
    [sys.executable, "app.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
time.sleep(2)

# 检查服务是否启动成功
if server.poll() is not None:
    print("Flask 服务启动失败，请检查错误日志")
    sys.exit(1)

print("Flask 服务已启动 (127.0.0.1:5000)")

# 建立 ngrok 公网隧道
print("正在建立公网隧道...")
public_url = ngrok.connect(5000, bind_tls=True)

print("\n" + "=" * 60)
print("  ✅ 公网服务已就绪！")
print("=" * 60)
print(f"\n  公网地址: {public_url}")
print(f"  健康检查: {public_url}/health")
print(f"  检测接口: {public_url}/detect (multipart)")
print(f"  检测接口: {public_url}/detect/raw (纯二进制)")
print(f"\n  把这个地址发给第三方调用方即可")
print("=" * 60)
print("\n按 Ctrl+C 停止服务\n")

try:
    # 保持运行
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n正在停止服务...")
    ngrok.kill()
    server.terminate()
    print("服务已停止")
