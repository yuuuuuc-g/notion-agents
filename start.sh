#!/bin/bash

# 1. 杀死旧的端口进程 (防止端口占用报错)
echo "🧹 Cleaning up old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null

# 2. 启动后端 (后台运行)
echo "🧠 Starting Exocortex Brain (FastAPI)..."
python -u server.py > /proc/1/fd/1 2>/proc/1/fd/2 &
SERVER_PID=$!

# 等待几秒让后端启动
sleep 5

# 3. 启动前端
echo "💻 Starting Client (Streamlit)..."
python -m streamlit run app.py

# 4. 退出时清理后台进程
kill $SERVER_PID