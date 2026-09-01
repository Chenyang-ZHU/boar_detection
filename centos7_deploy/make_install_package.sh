#!/bin/bash
# ============================================================
# 生成交付 ZIP 安装包（每次重建离线包后运行一次）
# Build delivery ZIP package (run after each offline package rebuild)
#
# 用法 / Usage:
#     bash make_install_package.sh
#
# 生成 / Produces:
#     /home/zcy/boar-centos7-offline/野猪检测安装包_YYYYMMDDHHMM.zip
#     内容：boar_env.tar.gz（环境，一次性构建）+ boar_scripts.tar.gz（脚本，每次改动重建）
#           + install_usb.sh + prepare_shim.sh + test_boar_640.jpg + 安装说明.txt
# ============================================================
set -euo pipefail

OFFLINE_DIR="/home/zcy/boar-centos7-offline"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TS=$(date '+%Y%m%d%H%M')
NEW_ZIP="$OFFLINE_DIR/野猪检测安装包_$TS.zip"

ENV_TAR="$OFFLINE_DIR/boar_env.tar.gz"
SCRIPTS_TAR="$OFFLINE_DIR/boar_scripts.tar.gz"

echo "=== 检查离线包（拆包格式）==="
[ -f "$ENV_TAR" ] || { echo "❌ 找不到环境包: $ENV_TAR"; exit 1; }
[ -f "$SCRIPTS_TAR" ] || { echo "❌ 找不到脚本包: $SCRIPTS_TAR"; exit 1; }
ls -lh "$ENV_TAR" "$SCRIPTS_TAR" | awk '{print "  " $5, $6, $7, $9}'

echo "=== 暂存 6 个交付文件 ==="
WORK=$(mktemp -d)
cp "$ENV_TAR" "$WORK/boar_env.tar.gz"
cp "$SCRIPTS_TAR" "$WORK/boar_scripts.tar.gz"
cp "$SCRIPT_DIR/install_usb.sh" "$WORK/"
cp "$SCRIPT_DIR/prepare_shim.sh" "$WORK/"
# 测试图：优先离线目录，否则仓库
if [ -f "$OFFLINE_DIR/test_boar_640.jpg" ]; then
  cp "$OFFLINE_DIR/test_boar_640.jpg" "$WORK/"
else
  cp "$REPO_ROOT/work/service/test_boar_640.jpg" "$WORK/"
fi
cp "$SCRIPT_DIR/安装说明.txt" "$WORK/"

echo "=== 备份旧 ZIP ==="
for z in "$OFFLINE_DIR"/野猪检测安装包_*.zip; do
  [ -e "$z" ] || continue
  base=$(basename "$z")
  # 跳过即将生成的新包；旧包改名为 _OLD_<ts>
  [ "$base" = "野猪检测安装包_$TS.zip" ] && continue
  oldname="野猪检测安装包_OLD_$TS.zip"
  [ "$base" = "$oldname" ] && continue
  mv "$z" "$OFFLINE_DIR/$oldname" && echo "  旧包已备份: $oldname"
done

echo "=== 打包 ==="
cd "$WORK"
zip -q "$NEW_ZIP" \
  boar_env.tar.gz \
  boar_scripts.tar.gz \
  install_usb.sh \
  prepare_shim.sh \
  test_boar_640.jpg \
  安装说明.txt
cd /
rm -rf "$WORK"

echo "======================================================"
echo " ✅ ZIP 已生成: $NEW_ZIP"
ls -lh "$NEW_ZIP" | awk '{print "   大小: " $5}'
echo "======================================================"
