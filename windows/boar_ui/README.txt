🐗 野猪检测工具 - Windows 部署包 v3
=====================================

使用 YOLOv8 检测红外相机照片中的野猪。
准确率 87%，召回率 82%。

使用方法
--------
1. 傻瓜安装请用 ../installer/（一键打包.bat + 安装到桌面.bat）
2. 技术员手动打包：双击 build.bat → 自动装依赖 + 打包 exe
3. 等待 10-15 分钟
4. 产出 dist\BoarDetector.exe

运行 exe 后:
  📷 检测单张图片  - 选图 → 自动标注 → 保存结果
  📁 批量检测图片  - 选文件夹 → 批量处理
  🎬 检测视频      - 逐帧分析 → 输出标注视频

参数:
  置信度阈值: 默认 0.25 (调高减少误报, 调低减少漏检)
  IoU 阈值:   默认 0.45 (一般不用调)

文件说明
--------
build.bat          ← 一键打包脚本 (技术员运行这个)
build_debug.bat    ← 调试用（显示完整报错）
run.bat            ← 直接以源码方式运行（需已装 Python + 依赖）
src/app.py         桌面 GUI 主程序
src/detector.py    ONNX 推理引擎
model/best.onnx    野猪检测模型 (12MB)
boar.ico           程序图标

技术栈: ONNX Runtime + OpenCV + PyInstaller
模型:   YOLOv8n | 564 张训练照 | 640x640 输入
验证:   已在 Linux 容器验证 ONNX 推理（测试图检出 2 头野猪，conf 0.94/0.77）
