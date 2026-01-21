#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 正在清理旧进程 (Port 8000)...${NC}"
# 只清理后端端口
lsof -ti:8000 | xargs kill -9 2>/dev/null

# 检查 .env 是否存在
if [ ! -f .env ]; then
    echo -e "${RED}❌ 错误: 未找到 .env 文件！请先创建配置。${NC}"
    exit 1
fi

echo -e "${GREEN}🧠 正在启动 BioBrain Backend (FastAPI)...${NC}"
echo -e "${BLUE}👉 API 文档地址: http://127.0.0.1:8000/docs${NC}"
echo -e "${BLUE}👉 监控指标地址: http://127.0.0.1:8000/metrics${NC}"
echo -e "---------------------------------------------------"

# 直接在前台运行 server.py
# 这样你可以直接看到所有 print 和 logger 的输出，Ctrl+C 即可停止
python -u server.py
