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

# 最大请求体大小（对齐视频上限 500MB）
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


def make_success_response(data: dict) -> tuple:
    """构造成功响应（HTTP 200 + code 0）"""
    return jsonify({"code": 0, "message": "success", "data": data})


def make_error_response(code: int, message: str) -> tuple:
    """构造错误响应（统一 HTTP 200，调用方以 code 区分）"""
    return jsonify({"code": code, "message": message, "data": None})


def make_media_response(data: bytes, headers: dict) -> tuple:
    """构造媒体流成功响应（headers 需含 Content-Type）"""
    return (data, 200, headers)


# ---------------------------------------------------------------------------
# POST /detect — 图像检测（multipart），返回坐标 JSON
# ---------------------------------------------------------------------------
@app.route("/detect", methods=["POST"])
def detect_multipart():
    """
    接收 multipart 上传的图片，返回检测坐标 JSON（归一化 bbox）。

    请求字段:
        image: 图片文件 (JPEG/PNG/BMP, 任意尺寸)

    响应:
        成功: HTTP 200, {"code":0, "message":"success", "data":{detections, image_width, image_height, inference_time_ms}}
        失败: HTTP 200, {"code":40001/50001, "message":"...", "data":null}
    """
    if "image" not in request.files:
        return make_error_response(40001, "请求中缺少 image 字段")

    file = request.files["image"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    return _detect_image(file.read())


# ---------------------------------------------------------------------------
# POST /detect/raw — 图像检测（纯二进制），返回坐标 JSON
# ---------------------------------------------------------------------------
@app.route("/detect/raw", methods=["POST"])
def detect_raw():
    """
    接收纯二进制图片，返回检测坐标 JSON（归一化 bbox）。

    请求头:
        Content-Type: image/jpeg 或 image/png 或 image/bmp

    请求体:
        图片二进制数据
    """
    image_data = request.get_data()
    if not image_data:
        return make_error_response(40001, "请求体为空")

    return _detect_image(image_data)


def _detect_image(image_data: bytes) -> tuple:
    """统一的图像检测处理函数，返回 JSON 坐标"""
    try:
        result = detector.detect_image_coords(image_data)
        return make_success_response(result)

    except ValueError as e:
        logger.warning(f"图像请求参数错误: {e}")
        return make_error_response(40001, str(e))

    except Exception as e:
        logger.error(f"图像推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"模型推理失败: {str(e)}")


# ---------------------------------------------------------------------------
# POST /detect/video/coords — 视频检测，返回逐帧坐标 JSON
# ---------------------------------------------------------------------------
@app.route("/detect/video/coords", methods=["POST"])
def detect_video_coords():
    """
    接收视频，逐帧检测后返回每帧坐标 JSON。

    请求字段:
        video: 视频文件 (mp4/avi/mov, 任意尺寸/时长)

    响应:
        成功: HTTP 200, {"code":0, "data":{frame_width, frame_height, fps,
              frame_count, duration_sec, frames:[{index, timestamp_ms, detections}]}}
    """
    if "video" not in request.files:
        return make_error_response(40001, "请求中缺少 video 字段")

    file = request.files["video"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    try:
        result = detector.detect_video_coords(file.read())
        return make_success_response(result)

    except ValueError as e:
        logger.warning(f"视频请求参数错误: {e}")
        return make_error_response(40001, str(e))

    except Exception as e:
        logger.error(f"视频推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"视频处理失败: {str(e)}")


# ---------------------------------------------------------------------------
# POST /detect/video — 视频检测，返回画框 mp4
# ---------------------------------------------------------------------------
@app.route("/detect/video", methods=["POST"])
def detect_video():
    """
    接收视频，逐帧检测后返回画了 bbox 的 mp4 视频。

    请求字段:
        video: 视频文件

    响应:
        成功: HTTP 200, Content-Type: video/mp4, body 为画框视频
              （响应头带 X-Original-Width/Height/Duration/Size）
        失败: HTTP 200, {"code":40001/50001, "message":"...", "data":null}
    """
    if "video" not in request.files:
        return make_error_response(40001, "请求中缺少 video 字段")

    file = request.files["video"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    try:
        video_bytes, meta = detector.detect_video(file.read())
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
        return make_error_response(40001, str(e))

    except Exception as e:
        logger.error(f"视频推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"视频处理失败: {str(e)}")


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
    logger.info("  POST /detect              — 图像检测 (multipart, 返回坐标 JSON)")
    logger.info("  POST /detect/raw          — 图像检测 (纯二进制, 返回坐标 JSON)")
    logger.info("  POST /detect/video/coords — 视频检测 (返回逐帧坐标 JSON)")
    logger.info("  POST /detect/video        — 视频检测 (返回画框 mp4)")
    logger.info("  GET  /health               — 健康检查")

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=False,
        threaded=True,  # 多线程处理请求
    )
