#!/bin/bash
# 觉醒系统 - 快速启动脚本
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "❌ 需要 Python 3，请先安装"
  exit 1
fi

# 安装依赖（首次运行）
if ! python3 -c "import fastapi" &>/dev/null; then
  echo "📦 安装依赖..."
  pip3 install -r requirements.txt -q
fi

echo "⚡ 启动觉醒系统..."
python3 launcher.py
