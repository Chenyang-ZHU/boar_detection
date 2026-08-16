# AI 服务协议约定

> 版本：v2.0（画框图片/视频返回）  
> 最后更新：2026-08-16

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
| `/detect` | POST | multipart，字段 `image` | **画框 JPEG 图片** |
| `/detect/raw` | POST | 纯二进制，`Content-Type: image/*` | **画框 JPEG 图片** |
| `/detect/video` | POST | multipart，字段 `video` | **画框 MP4 视频** |
| `/health` | GET | 无 | JSON 健康状态 |

> **成功响应是媒体文件（画框图片/视频），不再是 JSON 坐标。** 调用方把响应 body 直接存成 `.jpg` / `.mp4` 文件即可。
>
> **错误时返回 HTTP 4xx/5xx + JSON**（见第 5 节）。

---

## 3. 图像检测

### 3.1 POST /detect（multipart）

#### 请求

标准 HTTP 文件上传：

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
if resp.status_code == 200:
    with open("result.jpg", "wb") as f:
        f.write(resp.content)   # 画框图片字节
else:
    print(resp.json())          # 错误 JSON
```

#### 响应

- **成功（HTTP 200）**：`Content-Type: image/jpeg`，body 为画框后的 JPEG 图片；未检测到目标时返回原图。

  响应头（返回原始数据大小信息）：

  | 响应头 | 说明 |
  |--------|------|
  | `X-Original-Width` | 原始图片宽度（像素） |
  | `X-Original-Height` | 原始图片高度（像素） |
  | `X-Scale-Info` | （仅当自动缩放时）原始→处理的尺寸，如 `original 4000x3000 -> 2560x1920` |

- **失败（HTTP 4xx/5xx）**：JSON，见第 5 节。

### 3.2 POST /detect/raw（纯二进制）

#### 请求

图片二进制直接放在 body 中，适用于摄像头内存数据等场景：

```bash
curl -X POST http://{host}:5000/detect/raw \
  -H "Content-Type: image/jpeg" \
  --data-binary @图片路径.jpg
```

```python
import requests
image_data = camera_sdk.get_frame()  # bytes
resp = requests.post(
    "http://{host}:5000/detect/raw",
    data=image_data,
    headers={"Content-Type": "image/jpeg"},
    timeout=30,
)
if resp.status_code == 200:
    with open("result.jpg", "wb") as f:
        f.write(resp.content)
```

#### 响应

与 `/detect` 完全一致（画框 JPEG + 原始尺寸响应头）。

---

## 4. 视频检测

### 4.1 POST /detect/video

#### 请求

```bash
curl -X POST http://{host}:5000/detect/video \
  -m 120 \
  -F "video=@视频路径.mp4"
```

```python
import requests
resp = requests.post(
    "http://{host}:5000/detect/video",
    files={"video": open("视频路径.mp4", "rb")},
    timeout=120,
)
if resp.status_code == 200:
    with open("result.mp4", "wb") as f:
        f.write(resp.content)
else:
    print(resp.json())
```

#### 响应

- **成功（HTTP 200）**：`Content-Type: video/mp4`，body 为逐帧画框后的 MP4 视频。

  响应头：

  | 响应头 | 说明 |
  |--------|------|
  | `X-Original-Width` | 原始视频帧宽（像素） |
  | `X-Original-Height` | 原始视频帧高（像素） |
  | `X-Original-Duration` | 原始时长（秒） |
  | `X-Original-Size` | 原始文件大小（字节） |
  | `X-Scale-Info` | （仅当自动缩放时）原始→处理的尺寸 |

- **失败（HTTP 4xx/5xx）**：JSON，见第 5 节。

---

## 5. 错误响应

**错误时返回 HTTP 4xx/5xx + JSON**：

```json
{
  "code": 40001,
  "message": "图片过大（原始尺寸 9000×6000，原始数据大小 0.8MB），长边超过 8192px，请先压缩",
  "data": null
}
```

| HTTP 状态 | code | 含义 | 处理方法 |
|----------|------|------|---------|
| 400 | `40001` | 参数错误：格式不支持、尺寸/大小超限、时长超限、缺字段 | 按 message 提示修正 |
| 500 | `50001` | 模型推理/处理异常 | 稍后重试，持续失败请联系服务方 |

> 调用方应根据 **HTTP 状态码** 判断成功与否（2xx 成功，4xx/5xx 失败），错误详情在 JSON 的 `message` 中。

---

## 6. 媒体规格（接受任意尺寸，自动缩放）

### 6.1 图片

| 项目 | 规则 |
|------|------|
| 格式 | JPEG、PNG、BMP（按文件头魔数识别） |
| 尺寸 | **接受任意尺寸**；长边 > 2560px 时服务端**自动缩放**到 2560px 后检测 |
| 上限 | 长边 > 8192px 或文件 > 50MB → 返回 `40001` 说明（含原始尺寸） |
| 输出 | 画框 JPEG（质量 90） |

### 6.2 视频

| 项目 | 规则 |
|------|------|
| 格式 | mp4 / avi / mov / mkv 等（OpenCV/FFmpeg 可解码） |
| 尺寸 | **接受任意尺寸/时长**；帧长边 > 2560px 时**自动缩放**后检测 |
| 上限 | 文件 > 500MB 或时长 > 300 秒 → 返回 `40001` 说明（含原始时长/大小） |
| 输出 | 逐帧画框 MP4（编码优先 H.264，回退 mp4v） |

> **调用方无需自行缩放**：直接传原始图片/视频即可，服务端自动处理，并在响应头返回原始尺寸信息。

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

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 服务状态，"ok" 表示正常 |
| model_loaded | bool | 模型是否成功加载 |
| model | string | 当前加载的模型名称 |
| device | string | 推理设备，"cpu" 或 "cuda:0" |
| uptime_seconds | int | 服务已运行时长（秒） |

---

## 8. 调用方注意事项

### 8.1 超时设置

| 接口 | 建议超时 |
|------|---------|
| `/detect`、`/detect/raw` | 30 秒 |
| `/detect/video` | 120 秒 |

> 单张图片 Jetson GPU 推理约 130~160ms；视频逐帧检测约 46ms/帧，30 秒视频约需 40 秒处理。

### 8.2 输出文件

- 图像成功响应：直接把 body 存成 `.jpg`
- 视频成功响应：直接把 body 存成 `.mp4`

### 8.3 原始尺寸信息

- 响应头 `X-Original-Width` / `X-Original-Height` 始终返回输入图片/视频的原始像素尺寸
- 若发生自动缩放，`X-Scale-Info` 说明缩放前后尺寸
- 视频额外提供 `X-Original-Duration`（秒）和 `X-Original-Size`（字节）
