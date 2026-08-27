# AI 服务协议约定

> 版本：v2.2（视频 H.264 + 野猪信息响应头）  
> 最后更新：2026-08-25

---

## 1. 接口地址

| 环境 | 地址 |
|------|------|
| 本地开发 | `http://127.0.0.1:5000` |
| 局域网（Jetson） | `http://192.168.1.55:5000` |
| 公网（ngrok） | `https://stopper-trimmer-tavern.ngrok-free.dev` |

---

## 2. 接口一览

| 接口 | 方法 | 请求 | 成功响应 |
|------|------|------|---------|
| `/detect` | POST | multipart，字段 `image` | **检测坐标 JSON** |
| `/detect/raw` | POST | 纯二进制，`Content-Type: image/*` | **检测坐标 JSON** |
| `/detect/video/coords` | POST | multipart，字段 `video` | **逐帧检测坐标 JSON** |
| `/detect/video` | POST | multipart，字段 `video` | **画框 MP4 视频** |
| `/health` | GET | 无 | JSON 健康状态 |

> **所有响应统一 HTTP 200**，调用方以 `code` 字段区分业务状态（0=成功，非 0=失败）。成功时 `data` 为业务数据；失败时 `data` 为 null。

---

## 3. 图像检测（返回坐标）

### 3.1 POST /detect（multipart）

#### 请求

```bash
curl -X POST http://{host}:5000/detect \
  -F "image=@图片路径.jpg"
```

```python
import requests
resp = requests.post(
    "http://{host}:5000/detect",
    files={"image": open("图片路径.jpg", "rb")},
    timeout=30,
)
data = resp.json()   # 都是 HTTP 200，看 code
if data["code"] == 0:
    print(data["data"])
else:
    print(data["message"])
```

#### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "detections": [
      {
        "class": "boar",
        "class_id": 0,
        "confidence": 0.934,
        "bbox": {"x1": 0.10, "y1": 0.20, "x2": 0.50, "y2": 0.60}
      }
    ],
    "image_width": 1920,
    "image_height": 1080,
    "inference_time_ms": 95.3
  }
}
```

| 字段 | 说明 |
|------|------|
| `detections[]` | 检测目标列表；未检测到时为空数组 |
| `detections[].class` | 类别名（"boar"） |
| `detections[].class_id` | 类别 ID（0） |
| `detections[].confidence` | 置信度 0~1 |
| `detections[].bbox` | **归一化坐标**（0~1），相对原始图片尺寸 |
| `image_width` / `image_height` | 输入图片原始尺寸（像素） |
| `inference_time_ms` | 推理耗时（毫秒） |

**像素坐标还原**：`像素 = bbox × image_width/height`

### 3.2 POST /detect/raw（纯二进制）

图片二进制直接放 body，适用于摄像头内存数据：

```bash
curl -X POST http://{host}:5000/detect/raw \
  -H "Content-Type: image/jpeg" \
  --data-binary @图片路径.jpg
```

响应格式与 `/detect` 完全一致。

---

## 4. 视频检测（两种接口）

### 4.1 POST /detect/video/coords（逐帧坐标）

逐帧检测，返回每帧坐标，调用方可按 `index` / `timestamp_ms` 对应到原视频做跟踪/统计。

```bash
curl -X POST http://{host}:5000/detect/video/coords \
  -m 120 \
  -F "video=@视频路径.mp4"
```

#### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "frame_width": 1920,
    "frame_height": 1080,
    "fps": 20.0,
    "frame_count": 225,
    "duration_sec": 11.25,
    "frames": [
      {
        "index": 0,
        "timestamp_ms": 0.0,
        "detections": [
          {"class": "boar", "class_id": 0, "confidence": 0.93,
           "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6}}
        ]
      },
      {
        "index": 1,
        "timestamp_ms": 50.0,
        "detections": []
      }
    ]
  }
}
```

| 字段 | 说明 |
|------|------|
| `frame_width` / `frame_height` | 视频帧尺寸（像素） |
| `fps` | 帧率 |
| `frame_count` | 总帧数 |
| `duration_sec` | 视频时长（秒） |
| `total_detections` | 全视频累计检出次数（所有帧检出数累加） |
| `max_detections` | **单帧最多野猪数**（视频里单帧识别最多的数目，峰值） |
| `boar_present` | 是否有野猪（`true`/`false`） |
| `avg_confidence` | 检出平均置信度（0~1） |
| `frames[]` | 逐帧结果 |
| `frames[].index` | 帧序号（从 0 开始） |
| `frames[].timestamp_ms` | 该帧时间戳（毫秒） |
| `frames[].detections` | 该帧检测列表，未检测到为空数组；bbox 归一化 |

### 4.2 POST /detect/video（画框视频）

逐帧检测并画框，返回 MP4 视频。

```bash
curl -s -o /tmp/out.mp4 -m 120 \
  -X POST http://{host}:5000/detect/video \
  -F "video=@视频路径.mp4"
```

#### 成功响应

- HTTP 200，`Content-Type: video/mp4`，body 为画框视频字节，直接存成 `.mp4` 即可
- 响应头（返回原始数据大小信息）：

| 响应头 | 说明 |
|--------|------|
| `X-Original-Width` | 原始帧宽（像素） |
| `X-Original-Height` | 原始帧高（像素） |
| `X-Original-Duration` | 原始时长（秒） |
| `X-Original-Size` | 原始文件大小（字节） |
| `X-Boar-Count` | **单帧最多野猪数**（视频里单帧识别最多的数目，峰值） |
| `X-Boar-Present` | 是否有野猪（`true`/`false`） |
| `X-Boar-Avg-Conf` | 检出平均置信度（0~1） |

---

## 5. 响应与错误

**所有响应统一 HTTP 200**，以 `code` 区分：

```json
{ "code": 0,     "message": "success",             "data": { ... } }    // 成功
{ "code": 40001, "message": "错误说明",            "data": null }       // 参数错误
{ "code": 429001, "message": "服务繁忙，请稍后重试", "data": null }       // 并发超限
{ "code": 50001, "message": "模型推理失败: ...",    "data": null }       // 服务异常
{ "code": 50002, "message": "处理超时: ...",        "data": null }       // 处理超时
```

| code | 含义 | 处理方法 |
|------|------|---------|
| `0` | 成功 | — |
| `40001` | 参数错误：格式不支持、尺寸/大小超限、时长超限、缺字段 | 按 message 提示修正 |
| `429001` | **服务繁忙**：同时处理的请求数已达上限（并发限制） | **退避重试**（建议 3s 以上），不要立刻重发 |
| `50001` | 模型推理/处理异常 | 稍后重试，持续失败请联系服务方 |
| `50002` | 处理超时：单请求超过服务端处理时长上限 | 缩短视频/降低分辨率，或稍后重试 |

> **调用方协作约定（重要）**：
> - 调用方为**阻塞式调用**：收到 `429001` 后应**退避重试**（3s+），不要立刻重发，否则会触发持续繁忙
> - **图片超时建议 30s、视频超时建议 180s**（视频处理需 30~90s，超时太短必然失败）
> - 若调用方超时断开，服务端会**中止处理**该请求，请放心重发新请求（不会堆积）

常见错误 message：
- `不支持的图片格式，仅支持 JPEG/PNG/BMP`
- `图片过大（原始尺寸 9000×6000，原始数据大小 0.8MB），长边超过 8192px，请先压缩`
- `请求中缺少 image 字段`
- `视频时长 45.0 秒超过处理上限 300 秒（原始时长 45.0s，原始数据大小 12.0MB）`
- `无法读取视频，请确认视频格式为 mp4/avi/mov`

---

## 6. 媒体规格（接受任意尺寸，按原尺寸处理）

### 6.1 图片

| 项目 | 规则 |
|------|------|
| 格式 | JPEG、PNG、BMP（按文件头魔数识别） |
| 尺寸 | **接受任意尺寸**，按原始尺寸处理 |
| 上限 | 长边 > 8192px 或文件 > 50MB → 返回 `40001` 说明（含原始尺寸） |

### 6.2 视频

| 项目 | 规则 |
|------|------|
| 格式 | mp4 / avi / mov / mkv 等（OpenCV/FFmpeg 可解码） |
| 尺寸 | **接受任意尺寸/时长**，按原始分辨率逐帧处理 |
| 上限 | 文件 > 500MB 或时长 > 300 秒 → 返回 `40001` 说明（含原始时长/大小） |

> **调用方无需自行缩放**：直接传原始图片/视频即可。

---

## 7. 健康检查 — GET /health

```
GET http://{host}:5000/health
```

```json
{
  "status": "ok",
  "model_loaded": true,
  "model": "yolov8n_merged_final",
  "device": "cuda:0",
  "uptime_seconds": 3600
}
```

---

## 8. 调用方注意事项

### 8.1 超时设置

| 接口 | 建议超时 |
|------|---------|
| `/detect`、`/detect/raw` | 30 秒 |
| `/detect/video/coords` | 120 秒 |
| `/detect/video` | 120 秒 |

> 单张图片 Jetson GPU 推理约 130~160ms；视频逐帧检测约 46ms/帧，30 秒视频约需 40 秒处理。

### 8.2 输出

- 坐标接口：直接解析 `data` 里的 detections/bbox
- 画框视频接口：把响应 body 存成 `.mp4`，文件名由调用方自定义
- bbox 均为归一化坐标，还原像素 = `bbox × 对应边像素`
