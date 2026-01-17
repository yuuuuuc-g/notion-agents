# 1. 基础镜像
FROM python:3.11-slim

WORKDIR /app

# 2. 还原：安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    lsof \
    && rm -rf /var/lib/apt/lists/*

# 4. 还原：复制清单并使用阿里云源安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# 复制必要代码
COPY . .

# 权限处理
RUN chmod +x start.sh

# 暴露端口
EXPOSE 8000

# 启动 (沿用你之前的脚本)
CMD ["./start.sh"]
