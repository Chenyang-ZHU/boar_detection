# AI 服务协议约定

> 版本：v1.1  
> 最后更新：2026-07-27

---

## 1. 接口地址

| 环境 | 地址 |
|------|------|
| 本地开发 | `http://127.0.0.1:5000` |
| 生产环境 | 待定 |

---

## 2. 野猪检测接口

服务提供两种请求方式，调用方可任选其一：

| 接口 | 方式 | 适用场景 |
|------|------|---------|
| `POST /detect` | multipart/form-data | 需要附带额外参数（摄像头ID、时间戳等） |
| `POST /detect/raw` | 纯二进制（raw） | 只传图片，简单直接 |

两种接口的**响应格式完全一致**。

---

### 2.1 方式一：POST /detect（multipart）

#### 接口说明

标准 HTTP 文件上传方式，适合需要附带额外字段的场景。

#### 请求地址

```
POST http://{host}:5000/detect
```

#### 请求头

| 请求头 | 值 | 说明 |
|--------|-----|------|
| Content-Type | `multipart/form-data; boundary=----xxxx` | 标准文件上传格式，boundary 由调用方 HTTP 库自动生成 |

#### 请求字段

| 字段 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| `image` | body | file | 是 | 待检测的图片文件 |

#### 请求示例

**Python：**
```python
import requests

url = "http://127.0.0.1:5000/detect"
resp = requests.post(url, files={"image": open("capture_640.jpg", "rb")})
data = resp.json()
```

**curl：**
```bash
curl -X POST http://127.0.0.1:5000/detect \
  -F "image=@capture_640.jpg"
```

**Java（OkHttp）：**
```java
OkHttpClient client = new OkHttpClient();
RequestBody body = new MultipartBody.Builder()
    .setType(MultipartBody.FORM)
    .addFormDataPart("image", "capture.jpg",
        RequestBody.create(MediaType.parse("image/jpeg"), new File("capture_640.jpg")))
    .build();
Request request = new Request.Builder()
    .url("http://127.0.0.1:5000/detect")
    .post(body)
    .build();
Response resp = client.newCall(request).execute();
```

**C#：**
```csharp
using var httpClient = new HttpClient();
using var formData = new MultipartFormDataContent();
var imageContent = new ByteArrayContent(File.ReadAllBytes("capture_640.jpg"));
imageContent.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
formData.Add(imageContent, "image", "capture_640.jpg");
var resp = await httpClient.PostAsync("http://127.0.0.1:5000/detect", formData);
var json = await resp.Content.ReadAsStringAsync();
```

---

### 2.2 方式二：POST /detect/raw（纯二进制）

#### 接口说明

适用于监控平台等直接从内存获取图片的场景。**图片数据直接放在 HTTP body 中发送**，没有任何包装，调用方代码最简洁。

#### 请求地址

```
POST http://{host}:5000/detect/raw
```

#### 请求头

| 请求头 | 值 | 说明 |
|--------|-----|------|
| Content-Type | `image/jpeg` 或 `image/png` 或 `image/bmp` | **必填**，告知服务端图片编码格式 |

#### 请求体

直接将 640×640 图片的二进制数据放在 HTTP body 中，不包裹任何格式。

#### 请求示例

**Python（从摄像头内存数据直接发）：**
```python
import requests

# 直接从摄像头 SDK 拿到图片 bytes（不落盘）
image_data = camera_sdk.get_frame()  # bytes, 640×640 JPEG

resp = requests.post(
    "http://127.0.0.1:5000/detect/raw",
    data=image_data,
    headers={"Content-Type": "image/jpeg"}
)
data = resp.json()
```

**Python（从文件发）：**
```python
import requests

with open("capture_640.jpg", "rb") as f:
    image_data = f.read()

resp = requests.post(
    "http://127.0.0.1:5000/detect/raw",
    data=image_data,
    headers={"Content-Type": "image/jpeg"}
)
```

**curl：**
```bash
curl -X POST http://127.0.0.1:5000/detect/raw \
  -H "Content-Type: image/jpeg" \
  --data-binary @capture_640.jpg
```

**Java：**
```java
URL url = new URL("http://127.0.0.1:5000/detect/raw");
HttpURLConnection conn = (HttpURLConnection) url.openConnection();
conn.setRequestMethod("POST");
conn.setRequestProperty("Content-Type", "image/jpeg");
conn.setDoOutput(true);

byte[] imageBytes = Files.readAllBytes(Paths.get("capture_640.jpg"));
conn.getOutputStream().write(imageBytes);

int code = conn.getResponseCode();
// 读取响应...
```

**C#：**
```csharp
using var httpClient = new HttpClient();
var imageBytes = File.ReadAllBytes("capture_640.jpg");
var content = new ByteArrayContent(imageBytes);
content.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
var resp = await httpClient.PostAsync("http://127.0.0.1:5000/detect/raw", content);
var json = await resp.Content.ReadAsStringAsync();
```

**Node.js：**
```javascript
const fs = require('fs');
const http = require('http');

const imageBuffer = fs.readFileSync('capture_640.jpg');
const options = {
  hostname: '127.0.0.1',
  port: 5000,
  path: '/detect/raw',
  method: 'POST',
  headers: {
    'Content-Type': 'image/jpeg',
    'Content-Length': imageBuffer.length
  }
};
const req = http.request(options, res => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => console.log(JSON.parse(data)));
});
req.write(imageBuffer);
req.end();
```

---

### 2.3 图片规格（两种方式共用）

| 项目 | 要求 |
|------|------|
| 格式 | JPEG、PNG、BMP |
| 尺寸 | **长边不超过 1080px**，任意比例均可（服务端自动缩放至 640×640 进行推理） |
| 颜色空间 | RGB 或 BGR 均可 |
| 文件大小 | 建议控制在 1MB 以内 |

> 旧版本要求严格 640×640，现已取消。调用方无需自行缩放，**直接传入原始图片即可**。

---

### 2.4 成功响应

#### 检测到目标

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
        "bbox": {
          "x1": 0.10,
          "y1": 0.20,
          "x2": 0.50,
          "y2": 0.60
        }
      }
    ],
    "image_width": 640,
    "image_height": 640,
    "inference_time_ms": 95.3
  }
}
```

#### 未检测到目标

图片中没有野猪时，`detections` 字段返回空数组：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "detections": [],
    "image_width": 640,
    "image_height": 640,
    "inference_time_ms": 98.1
  }
}
```

---

### 2.5 响应字段说明

#### 外层字段

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| code | int | 见错误码表 | 业务状态码，0 表示成功 |
| message | string | — | 状态描述，成功时为 "success" |
| data | object / null | — | 业务数据，成功时返回数据，失败时为 null |

#### data 字段

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| detections | array | — | 检测结果列表，每项对应一个检测到的目标 |
| image_width | int | 固定 640 | 输入图片宽度 |
| image_height | int | 固定 640 | 输入图片高度 |
| inference_time_ms | float | ≥ 0 | 模型推理耗时，单位毫秒 |

#### detections[] 元素

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| class | string | "boar" | 目标类别名称 |
| class_id | int | 0 | 目标类别 ID（目前仅 boar 一个类别） |
| confidence | float | 0~1 | 置信度，越接近 1 表示模型越确信是野猪 |
| bbox | object | 见下 | 检测框坐标，**归一化坐标**（范围 0~1） |

#### bbox 字段

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| x1 | float | 0~1 | 检测框左上角 X 坐标（归一化） |
| y1 | float | 0~1 | 检测框左上角 Y 坐标（归一化） |
| x2 | float | 0~1 | 检测框右下角 X 坐标（归一化） |
| y2 | float | 0~1 | 检测框右下角 Y 坐标（归一化） |

**坐标说明：** 所有 bbox 均为归一化坐标（范围 0~1），相对于图片宽高比例。

**还原为实际像素坐标：**
```
像素_x1 = bbox.x1 × 图片宽度（640）
像素_y1 = bbox.y1 × 图片高度（640）
像素_x2 = bbox.x2 × 图片宽度（640）
像素_y2 = bbox.y2 × 图片高度（640）
```

示例：
```python
# 假设返回的 bbox
bbox = {"x1": 0.10, "y1": 0.20, "x2": 0.50, "y2": 0.60}
W, H = 640, 640   # 即 image_width, image_height

pixel_x1 = int(bbox["x1"] * W)  # 64
pixel_y1 = int(bbox["y1"] * H)  # 128
pixel_x2 = int(bbox["x2"] * W)  # 320
pixel_y2 = int(bbox["y2"] * H)  # 384
```

---

### 2.6 错误响应

所有错误响应统一通过 HTTP 200 返回，调用方通过 `code` 字段区分业务状态。

#### 格式

```json
{
  "code": 40004,
  "message": "图片尺寸必须是 640×640，实际为 1920×1080",
  "data": null
}
```

#### 各错误码的响应示例

**40001 — 不支持的图片格式：**
```json
{
  "code": 40001,
  "message": "不支持的图片格式，仅支持 JPEG/PNG/BMP",
  "data": null
}
```

**40004 — 图片尺寸错误：**
```json
{
  "code": 40004,
  "message": "图片尺寸必须是 640×640，实际为 1920×1080",
  "data": null
}
```

**50001 — 模型推理异常：**
```json
{
  "code": 50001,
  "message": "模型推理失败: CUDA out of memory",
  "data": null
}
```

---

## 3. 健康检查 — GET /health

### 3.1 接口说明

用于探测服务是否存活，以及获取服务基本信息。

#### 请求地址

```
GET http://{host}:5000/health
```

#### 请求参数

无。

#### 成功响应

```json
{
  "status": "ok",
  "model_loaded": true,
  "model": "yolov8n_merged_final",
  "device": "cpu",
  "uptime_seconds": 3600
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 服务状态，"ok" 表示正常 |
| model_loaded | bool | 模型是否成功加载 |
| model | string | 当前加载的模型名称 |
| device | string | 推理设备，"cpu" 或 "cuda:0" |
| uptime_seconds | int | 服务已运行时长（秒） |

---

## 4. 错误码

| code | 含义 | HTTP 状态码 | 调用方处理建议 |
|------|------|------------|---------------|
| 0 | 成功 | 200 | — |
| 40001 | 不支持的图片格式或图片过大 | 200 | 确保图片为 JPEG/PNG/BMP，长边不超过 1080px |
| 50001 | 模型推理异常 | 200 | 稍后重试，若持续失败请联系服务方 |
| 50002 | 服务器内部错误 | 200 | 稍后重试，若持续失败请联系服务方 |

> 所有响应均为 HTTP 200，以 `code` 字段区分业务状态。调用方应根据 `code` 做业务逻辑判断，不要依赖 HTTP 状态码。

---

## 5. 两种方式对比

| 对比项 | POST /detect（multipart） | POST /detect/raw（纯二进制） |
|--------|--------------------------|----------------------------|
| 请求体 | 图片 + 表单包装（多几百字节） | 只有图片二进制数据 |
| 请求头 | `Content-Type: multipart/form-data` | `Content-Type: image/jpeg` |
| 附带额外字段 | ✅ 方便扩展（如 camera_id） | ❌ 不支持 |
| 调用方代码量 | 稍多 | 最简洁 |
| 适用场景 | 需要传图片以外的参数 | 只传图片，简单直接 |

> 建议：如果只需要传图片，优先使用 `/detect/raw`。

---

## 6. 调用方注意事项

### 6.1 图片尺寸

- 传入图片**长边不超过 1080px**，任意比例均可
- 服务端会自动将图片缩放至 640×640 进行推理，**调用方无需自行缩放**
- 返回的 bbox 坐标为**相对于原始图片尺寸**的归一化坐标，调用方按需还原
- 如果图片超出限制，服务端将返回 `code: 40001`

### 6.2 超时设置

| 场景 | 建议超时时间 |
|------|------------|
| 正常推理 | 5 秒 |
| 网络波动 | 30 秒（推荐） |

单张图片 CPU 推理耗时约 100 毫秒，建议调用方设置 30 秒超时作为安全余量。

### 6.3 坐标格式

- 返回的 bbox 为**归一化坐标**（范围 0~1），而非原始像素坐标
- 如需像素坐标，请按上述公式乘以图片宽高（640×640）还原
- 归一化的好处是分辨率变化时不需要修改接口返回值

### 6.4 并发说明

- 服务端单线程 CPU 推理，单张图片约 100ms，约 **10 QPS**
- 如需批量检测多张图片，建议调用方并发发送多个请求
- 如果对性能有更高要求，服务方可启用 GPU 加速（需部署环境有 GPU），届时单张推理约 10~15ms

### 6.5 请求图片准备建议（图片缩放）

调用方在发送前，需要将原始图片缩放到 640×640。推荐做法：

```python
import cv2

def prepare_image(input_path, output_path):
    """将任意尺寸图片缩放为 640×640（letterbox 方式）"""
    img = cv2.imread(input_path)
    h, w = img.shape[:2]
    scale = 640 / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h))
    
    # 创建 640×640 黑色画布，将缩放后的图片居中放置
    canvas = np.zeros((640, 640, 3), dtype=np.uint8)
    y_offset = (640 - new_h) // 2
    x_offset = (640 - new_w) // 2
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
    
    cv2.imwrite(output_path, canvas)
```
