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

# 最大请求体大小（图像 + 视频上传）
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB


def make_error_response(status_code: int, code: int, message: str) -> tuple:
    """构造错误响应（JSON）"""
    return (
        jsonify({"code": code, "message": message, "data": None}),
        status_code,
    )


def make_media_response(data: bytes, headers: dict) -> tuple:
    """构造媒体流成功响应（headers 需含 Content-Type）"""
    return (data, 200, headers)


# ---------------------------------------------------------------------------
# POST /detect — multipart/form-data 方式（图像）
# ---------------------------------------------------------------------------
@app.route("/detect", methods=["POST"])
def detect_multipart():
    """
    接收 multipart/form-data 方式上传的图片，返回画了 bbox 的 JPEG 图片。

    请求字段:
        image: 图片文件 (JPEG/PNG/BMP, 长边 ≤ 1080px)

    响应:
        成功: HTTP 200, Content-Type: image/jpeg, body 为画框图片
        失败: HTTP 4xx/5xx, body 为 JSON 错误信息
    """
    # 检查请求中是否包含图片
    if "image" not in request.files:
        return make_error_response(400, 40001, "请求中缺少 image 字段")

    file = request.files["image"]
    if file.filename == "":
        return make_error_response(400, 40001, "上传的文件名为空")

    image_data = file.read()
    return _detect_image(image_data)


# ---------------------------------------------------------------------------
# POST /detect/raw — 纯二进制方式（图像）
# ---------------------------------------------------------------------------
@app.route("/detect/raw", methods=["POST"])
def detect_raw():
    """
    接收纯二进制图片数据，返回画了 bbox 的 JPEG 图片。

    请求头:
        Content-Type: image/jpeg 或 image/png 或 image/bmp

    请求体:
        图片二进制数据

    响应:
        成功: HTTP 200, Content-Type: image/jpeg, body 为画框图片
        失败: HTTP 4xx/5xx, body 为 JSON 错误信息
    """
    image_data = request.get_data()
    if not image_data:
        return make_error_response(400, 40001, "请求体为空")

    return _detect_image(image_data)


def _detect_image(image_data: bytes) -> tuple:
    """统一的图像检测处理函数，返回画框 JPEG + 原始尺寸响应头"""
    try:
        jpeg_bytes, meta = detector.detect_image(image_data)
        headers = {
            "Content-Type": "image/jpeg",
            "X-Original-Width": str(meta["original_width"]),
            "X-Original-Height": str(meta["original_height"]),
        }
        return make_media_response(jpeg_bytes, headers)

    except ValueError as e:
        # 参数错误（图片格式不对、尺寸不对）
        logger.warning(f"图像请求参数错误: {e}")
        return make_error_response(400, 40001, str(e))

    except Exception as e:
        # 服务端异常
        logger.error(f"图像推理异常: {e}", exc_info=True)
        return make_error_response(500, 50001, f"模型推理失败: {str(e)}")


# ---------------------------------------------------------------------------
# POST /detect/video — 视频检测
# ---------------------------------------------------------------------------
@app.route("/detect/video", methods=["POST"])
def detect_video():
    """
    接收视频文件，逐帧检测后返回画了 bbox 的 mp4 视频。

    请求字段:
        video: 视频文件 (mp4/avi/mov, ≤30秒, ≤50MB)

    响应:
        成功: HTTP 200, Content-Type: video/mp4, body 为画框视频
        失败: HTTP 4xx/5xx, body 为 JSON 错误信息
    """
    if "video" not in request.files:
        return make_error_response(400, 40001, "请求中缺少 video 字段")

    file = request.files["video"]
    if file.filename == "":
        return make_error_response(400, 40001, "上传的文件名为空")

    video_data = file.read()

    try:
        video_bytes, meta = detector.detect_video(video_data)
        headers = {
            "Content-Type": "video/mp4",
            "X-Original-Width": str(meta["original_width"]),
            "X-Original-Height": str(meta["original_height"]),
            "X-Original-Duration": str(meta["original_duration"]),
            "X-Original-Size": str(meta["original_size"]),
        }
        return make_media_response(video_bytes, headers)

    except ValueError as e:
        logger.warning(f"视频请求参数错误: {e}")
        return make_error_response(400, 40001, str(e))

    except Exception as e:
        logger.error(f"视频推理异常: {e}", exc_info=True)
        return make_error_response(500, 50001, f"视频处理失败: {str(e)}")


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
    logger.info("接口列表:")
    logger.info("  POST /detect         — 图像检测 (multipart, 返回画框图)")
    logger.info("  POST /detect/raw     — 图像检测 (纯二进制, 返回画框图)")
    logger.info("  POST /detect/video   — 视频检测 (multipart, 返回画框视频)")
    logger.info("  GET  /health          — 健康检查")

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=False,
        threaded=True,  # 多线程处理请求
    )
