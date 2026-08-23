"""野猪检测 HTTP 服务 — Flask 主应用（健壮性加固版）"""

import time
import logging
import threading

from flask import Flask, request, jsonify
from waitress import serve

import config
from detector import BoarDetector, ClientDisconnected, ProcessingTimeout

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

# 并发限流信号量：同时最多处理 MAX_INFERENCE_WORKERS 个请求，满员立即返回繁忙
_inference_semaphore = threading.BoundedSemaphore(config.MAX_INFERENCE_WORKERS)


def make_success_response(data: dict) -> tuple:
    """构造成功响应（HTTP 200 + code 0）"""
    return jsonify({"code": 0, "message": "success", "data": data})


def make_error_response(code: int, message: str) -> tuple:
    """构造错误响应（统一 HTTP 200，调用方以 code 区分）"""
    return jsonify({"code": code, "message": message, "data": None})


def make_media_response(data: bytes, headers: dict) -> tuple:
    """构造媒体流成功响应（headers 需含 Content-Type）"""
    return (data, 200, headers)


def _busy_response() -> tuple:
    """服务繁忙响应（并发超限）"""
    return make_error_response(
        429001,
        f"服务繁忙，当前正在处理请求，请稍后重试（并发上限 {config.MAX_INFERENCE_WORKERS}）",
    )


def _with_capacity(handler, *args, **kwargs):
    """限流包装：信号量满员立即返回繁忙，不排队"""
    if not _inference_semaphore.acquire(blocking=False):
        logger.warning("并发超限，返回繁忙")
        return _busy_response()
    try:
        return handler(*args, **kwargs)
    finally:
        _inference_semaphore.release()


def _get_is_closed():
    """返回"客户端是否已断开"的检测函数。

    waitress 在 environ["waitress.client_disconnected"] 提供一个 callable；
    非 waitress 环境（如 werkzeug 开发服务器）下不存在该键，返回 None（不检测断开）。
    """
    try:
        check = request.environ.get("waitress.client_disconnected")
        return check if callable(check) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POST /detect — 图像检测（multipart），返回坐标 JSON
# ---------------------------------------------------------------------------
@app.route("/detect", methods=["POST"])
def detect_multipart():
    if "image" not in request.files:
        return make_error_response(40001, "请求中缺少 image 字段")

    file = request.files["image"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    return _with_capacity(_detect_image, file.read())


# ---------------------------------------------------------------------------
# POST /detect/raw — 图像检测（纯二进制），返回坐标 JSON
# ---------------------------------------------------------------------------
@app.route("/detect/raw", methods=["POST"])
def detect_raw():
    image_data = request.get_data()
    if not image_data:
        return make_error_response(40001, "请求体为空")

    return _with_capacity(_detect_image, image_data)


def _detect_image(image_data: bytes) -> tuple:
    """统一的图像检测处理函数，返回 JSON 坐标"""
    try:
        result = detector.detect_image_coords(image_data, timeout=config.IMAGE_PROCESS_TIMEOUT)
        return make_success_response(result)

    except ValueError as e:
        logger.warning(f"图像请求参数错误: {e}")
        return make_error_response(40001, str(e))

    except ProcessingTimeout as e:
        logger.warning(f"图像处理超时: {e}")
        return make_error_response(50002, str(e))

    except Exception as e:
        logger.error(f"图像推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"模型推理失败: {str(e)}")


# ---------------------------------------------------------------------------
# POST /detect/video/coords — 视频检测，返回逐帧坐标 JSON
# ---------------------------------------------------------------------------
@app.route("/detect/video/coords", methods=["POST"])
def detect_video_coords():
    if "video" not in request.files:
        return make_error_response(40001, "请求中缺少 video 字段")

    file = request.files["video"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    return _with_capacity(
        _detect_video_coords, file.read(), _get_is_closed(), config.VIDEO_PROCESS_TIMEOUT
    )


def _detect_video_coords(video_data: bytes, is_closed, timeout: float) -> tuple:
    """视频逐帧检测，返回坐标 JSON；支持客户端断开中止 + 处理超时"""
    try:
        result = detector.detect_video_coords(video_data, is_closed=is_closed, timeout=timeout)
        return make_success_response(result)

    except ValueError as e:
        logger.warning(f"视频请求参数错误: {e}")
        return make_error_response(40001, str(e))

    except ProcessingTimeout as e:
        logger.warning(f"视频处理超时: {e}")
        return make_error_response(50002, str(e))

    except ClientDisconnected:
        # 客户端已断开，响应无法送达，记录后返回即可
        logger.info("视频坐标处理：客户端已断开，已中止")
        return make_error_response(50002, "客户端已断开")

    except Exception as e:
        logger.error(f"视频推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"视频处理失败: {str(e)}")


# ---------------------------------------------------------------------------
# POST /detect/video — 视频检测，返回画框 mp4
# ---------------------------------------------------------------------------
@app.route("/detect/video", methods=["POST"])
def detect_video():
    if "video" not in request.files:
        return make_error_response(40001, "请求中缺少 video 字段")

    file = request.files["video"]
    if file.filename == "":
        return make_error_response(40001, "上传的文件名为空")

    return _with_capacity(
        _detect_video_file, file.read(), _get_is_closed(), config.VIDEO_PROCESS_TIMEOUT
    )


def _detect_video_file(video_data: bytes, is_closed, timeout: float) -> tuple:
    """视频逐帧检测，返回画框 mp4；支持客户端断开中止 + 处理超时"""
    try:
        video_bytes, meta = detector.detect_video(video_data, is_closed=is_closed, timeout=timeout)
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

    except ProcessingTimeout as e:
        logger.warning(f"视频处理超时: {e}")
        return make_error_response(50002, str(e))

    except ClientDisconnected:
        logger.info("视频画框处理：客户端已断开，已中止")
        return make_error_response(50002, "客户端已断开")

    except Exception as e:
        logger.error(f"视频推理异常: {e}", exc_info=True)
        return make_error_response(50001, f"视频处理失败: {str(e)}")


# ---------------------------------------------------------------------------
# GET /health — 健康检查
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    uptime = int(time.time() - app_start_time)
    return jsonify({
        "status": "ok",
        "model_loaded": detector.model is not None,
        "model": "yolov8n_merged_final",
        "device": detector.device,
        "uptime_seconds": uptime,
        "busy_requests": config.MAX_INFERENCE_WORKERS - _inference_semaphore._value,
    })


# ---------------------------------------------------------------------------
# 启动入口（waitress 生产服务器）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"启动服务: http://{config.HOST}:{config.PORT} (waitress, threads={config.WAITRESS_THREADS})")
    logger.info("接口列表:")
    logger.info("  POST /detect              — 图像检测 (multipart, 返回坐标 JSON)")
    logger.info("  POST /detect/raw          — 图像检测 (纯二进制, 返回坐标 JSON)")
    logger.info("  POST /detect/video/coords — 视频检测 (返回逐帧坐标 JSON)")
    logger.info("  POST /detect/video        — 视频检测 (返回画框 mp4)")
    logger.info("  GET  /health               — 健康检查")

    serve(
        app,
        host=config.HOST,
        port=config.PORT,
        threads=config.WAITRESS_THREADS,
        # 必须 >0 才能启用客户端断开检测（waitress.client_disconnected）
        # 否则调用方超时断开后服务无法感知，会继续处理已放弃的请求
        channel_request_lookahead=65536,
    )
