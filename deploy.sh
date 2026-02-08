#!/bin/bash

# ==========================================
# BioBrain 快速部署脚本
# ==========================================

set -e  # 遇到错误立即退出

echo "🚀 BioBrain 项目快速部署脚本"
echo "================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python 版本
echo "📌 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.9.0"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}❌ Python 版本过低: $python_version (需要 >= 3.9)${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 版本: $python_version${NC}"

# 检查 Redis
echo ""
echo "📌 检查 Redis..."
if ! command -v redis-cli &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis 未安装，请先安装 Redis:${NC}"
    echo "   Ubuntu/Debian: sudo apt-get install redis-server"
    echo "   macOS: brew install redis"
    exit 1
fi

if ! redis-cli ping &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis 未运行，正在启动...${NC}"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo systemctl start redis
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start redis
    fi
fi
echo -e "${GREEN}✅ Redis 运行正常${NC}"

# 创建虚拟环境
echo ""
echo "📌 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✅ 虚拟环境已创建${NC}"
else
    echo -e "${YELLOW}ℹ️  虚拟环境已存在${NC}"
fi

# 激活虚拟环境
echo ""
echo "📌 激活虚拟环境..."
source venv/bin/activate
echo -e "${GREEN}✅ 虚拟环境已激活${NC}"

# 安装依赖
echo ""
echo "📌 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✅ 依赖安装完成${NC}"

# 配置环境变量
echo ""
echo "📌 配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  已创建 .env 文件，请填写以下必需配置:${NC}"
    echo ""
    echo "   1. SILICON_KEY - SiliconFlow API Key"
    echo "   2. NOTION_TOKEN - Notion API Token"
    echo "   3. API_SECRET - Session 密钥 (至少 32 字符)"
    echo "   4. REDIS_PASSWORD - Redis 密码"
    echo "   5. DB_SPANISH_ID - Notion 数据库 ID"
    echo ""
    echo "   生成 API_SECRET: openssl rand -hex 32"
    echo ""

    # 自动生成 API_SECRET
    api_secret=$(openssl rand -hex 32)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/API_SECRET=.*/API_SECRET=$api_secret/" .env
    else
        sed -i "s/API_SECRET=.*/API_SECRET=$api_secret/" .env
    fi
    echo -e "${GREEN}✅ 已自动生成 API_SECRET${NC}"

    echo ""
    echo -e "${RED}⚠️  请编辑 .env 文件填写其他配置后再继续！${NC}"
    echo ""
    exit 0
else
    echo -e "${GREEN}✅ .env 文件已存在${NC}"
fi

# 验证配置
echo ""
echo "📌 验证配置..."
required_vars=("SILICON_KEY" "NOTION_TOKEN" "API_SECRET" "DB_SPANISH_ID")
missing_vars=()

for var in "${required_vars[@]}"; do
    value=$(grep "^$var=" .env | cut -d '=' -f2)
    if [ -z "$value" ] || [ "$value" == "your-"* ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo -e "${RED}❌ 以下配置项缺失或未填写:${NC}"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "请编辑 .env 文件填写这些配置项"
    exit 1
fi
echo -e "${GREEN}✅ 配置验证通过${NC}"

# 创建必要的目录
echo ""
echo "📌 创建必要的目录..."
mkdir -p audio_files
mkdir -p logs
mkdir -p backups
echo -e "${GREEN}✅ 目录创建完成${NC}"

# 备份原文件
echo ""
echo "📌 备份原始文件..."
if [ -f "server.py" ]; then
    timestamp=$(date +%Y%m%d_%H%M%S)
    mkdir -p "backups/$timestamp"
    cp server.py "backups/$timestamp/"
    [ -f "config/settings.py" ] && cp config/settings.py "backups/$timestamp/"
    [ -f "services/file_parser.py" ] && cp services/file_parser.py "backups/$timestamp/"
    echo -e "${GREEN}✅ 备份完成: backups/$timestamp/${NC}"
fi

# 运行测试
echo ""
echo "📌 运行测试..."
if python -m pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✅ 测试通过${NC}"
else
    echo -e "${YELLOW}⚠️  测试发现问题，请查看测试输出${NC}"
fi

# 完成
echo ""
echo "================================"
echo -e "${GREEN}🎉 部署准备完成！${NC}"
echo ""
echo "下一步:"
echo ""
echo "1. 启动开发服务器:"
echo "   python server.py"
echo ""
echo "2. 或使用 uvicorn:"
echo "   uvicorn server:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "3. 访问 API 文档:"
echo "   http://localhost:8000/docs"
echo ""
echo "4. 健康检查:"
echo "   curl http://localhost:8000/health"
echo ""
echo "================================"
