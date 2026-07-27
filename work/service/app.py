"""野猪检测 HTTP 服务 — Flask 主应用"""

import time
import logging

from flask import Flask, request, jsonify

import config
from detector import BoarDetector

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

# 创建 Flask 应用
app = Flask(__name__)

# 全局加载检测器（服务启动时加载模型并预热）
logger.info("正在初始化野猪检测服务...")
detector = BoarDetector()
app_start_time = time.time()


def make_success_response(data: dict) -> tuple:
    """构造成功响应"""
    return jsonify({"code": 0, "message": "success", "data": data})


def make_error_response(code: int, message: str) -> tuple:
    """构造错误响应"""
    return jsonify({"code": code, "message": message, "data": None})


# ---------------------------------------------------------------------------
# POST /detect — multipart/form-data 方式
# ---------------------------------------------------------------------------
@app.route("/detect", methods=["POST"])
def detect_multipart():
    """
    接收 multipart/form-data 方式上传的图片，执行目标检测。

    请求字段:
        image: 图片文件 (JPEG/PNG/BMP, 640×640)

    响应:
        成功: {"code": 0, "message": "success", "data": {...}}
        失败: {"code": 4xxxx/5xxxx, "message": "...", "data": null}
    """
    # 检查请求中是否包含图片
    if "image" not in request.files:
        return make_error_response(40001, "请求中缺少 image 字段")

    file = request.files["image"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    image_data = file.read()
    return _detect(image_data)


# ---------------------------------------------------------------------------
# POST /detect/raw — 纯二进制方式
# ---------------------------------------------------------------------------
@app.route("/detect/raw", methods=["POST"])
def detect_raw():
    """
    接收纯二进制图片数据（body 直接为图片内容），执行目标检测。

    请求头:
        Content-Type: image/jpeg 或 image/png 或 image/bmp

    请求体:
        图片二进制数据

    响应:
        成功: {"code": 0, "message": "success", "data": {...}}
        失败: {"code": 4xxxx/5xxxx, "message": "...", "data": null}
    """
    image_data = request.get_data()
    if not image_data:
        return make_error_response(40001, "请求体为空")

    # 校验 Content-Type
    content_type = request.content_type or ""
    if not any(fmt in content_type for fmt in ["image/jpeg", "image/png", "image/bmp", "image/x-"]):
        logger.warning(f"未识别的 Content-Type: {content_type}，尝试自动识别格式")

    return _detect(image_data)


def _detect(image_data: bytes) -> tuple:
    """统一的检测处理函数"""
    try:
        result = detector.detect(image_data)
        elapsed_ms = result["inference_time_ms"]
        det_count = len(result["detections"])
        logger.info(f"检测完成: {det_count} 个目标, 耗时 {elapsed_ms:.1f}ms")
        return make_success_response(result)

    except ValueError as e:
        # 参数错误（图片格式不对、尺寸不对）— 业务异常
        logger.warning(f"请求参数错误: {e}")
        return make_error_response(40001, str(e))

    except Exception as e:
        # 服务端异常
        logger.error(f"推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"模型推理失败: {str(e)}")


# ---------------------------------------------------------------------------
# GET /health — 健康检查
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    uptime = int(time.time() - app_start_time)
    return jsonify({
        "status": "ok",
        "model_loaded": detector.model is not None,
        "model": "yolov8n_merged_final",
        "device": detector.device,
        "uptime_seconds": uptime,
    })


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"启动服务: http://{config.HOST}:{config.PORT}")
    logger.info(f"接口列表:")
    logger.info(f"  POST /detect      — multipart 方式上传图片")
    logger.info(f"  POST /detect/raw   — 纯二进制方式上传图片")
    logger.info(f"  GET  /health       — 健康检查")

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=False,
        threaded=True,  # 多线程处理请求
    )
