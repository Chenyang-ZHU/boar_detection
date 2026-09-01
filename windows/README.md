# Windows 傻瓜 EXE 构建套件

把野猪检测服务打包成**单文件 EXE**，目标机**什么都不用安装**，双击即运行。

## 产物

`dist\野猪检测服务.exe` —— 复制到任何 Windows（7/10/11）双击即运行。

## 构建（只需在一台 Windows 机器上做一次）

### 1. 准备

- 一台 Windows 机器（装了 Python 3.10，勾选 "Add Python to PATH"）
- 把整个仓库（含 `windows\`、`work\service\`、模型文件）拷到这台 Windows

### 2. 构建

```bat
cd windows
build_exe.bat
```

脚本自动：
1. 装依赖（torch CPU / ultralytics / waitress / imageio-ffmpeg / qtfaststart / flask / pyinstaller）
2. 用 Windows 配置覆盖（构建后自动恢复）
3. PyInstaller 打包 → `dist\野猪检测服务.exe`

> 首次构建约 5-15 分钟，产物约 300-500MB（含 Python + torch + opencv 等全部依赖）。

### 3. 交付

把 `dist\野猪检测服务.exe` 拷给甲方，双击即运行。无需安装任何东西。

## 文件说明

| 文件 | 作用 |
|------|------|
| `boar_detection.spec` | PyInstaller 打包配置（捆绑模型 + ffmpeg） |
| `build_exe.bat` | 一键构建脚本 |
| `config.windows.py` | Windows 版配置（路径自动适配 exe 环境） |
| `使用说明.txt` | 给甲方看的说明 |

## ⚠️ 注意事项

- **必须在 Windows 上构建**：PyInstaller 不能跨平台（Linux 生成不了 Windows exe）
- **torch 用 CPU 版**：`--index-url https://download.pytorch.org/whl/cpu`（避免 CUDA 版本坑）
- **模型文件**：best.pt 已捆绑进 EXE；若单独放同目录也能识别
- **杀毒软件**：首次运行可能提示"未知发布者"，需"仍要运行"或加白名单
- **首次构建可能需微调 spec**：torch/ultralytics 打包偶有隐藏依赖问题，若构建报错，把输出发给技术人员
