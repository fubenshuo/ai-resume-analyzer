"""
阿里云函数计算 FC 入口

将 FastAPI 应用包装为 FC 兼容的 ASGI handler。
使用阿里云 FC Custom Runtime + HTTP 触发器部署。

部署步骤见 README.md
"""

import os
import sys

# 确保当前目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app

# FC Custom Runtime 需要直接暴露 ASGI app
# 启动命令由 bootstrap 文件指定：uvicorn app_FC:app --host 0.0.0.0 --port 9000
