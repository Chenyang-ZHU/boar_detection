#!/bin/bash

# 野猪检测标注/审核工具启动脚本

cd "$(dirname "$0")"

echo "🐗 启动野猪检测标注审核工具..."
echo ""
echo "📖 使用说明："
echo "   - 打开浏览器访问: http://localhost:5000"
echo "   - 在顶部选择数据集（手工标注 / 预标注帧 / 浦口图片 / 野猪图片 / merged）"
echo "   - 画框: D 绘制模式；选择: S；删除: Delete；保存: Ctrl+S"
echo "   - 审核通过: 点击 [✅ 已审核 → merged] 把当前图+标签并入 work/merged"
echo "   - 按 Ctrl+C 停止服务"
echo ""

python label_tool.py
