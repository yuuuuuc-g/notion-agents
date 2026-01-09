# 1. 基础镜像
FROM python:3.10-slim

# 2. 设置工作目录
WORKDIR /app

# 🔥 关键修改：换源！
# 把默认的 deb.debian.org 替换为 mirrors.aliyun.com
# 这样 apt-get install ffmpeg 就会飞快
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# 3. 安装系统依赖 (ffmpeg, lsof)
# 加上 --fix-missing 防止偶尔的网络抖动
RUN apt-get update && apt-get install -y --fix-missing \
    ffmpeg \
    lsof \
    && rm -rf /var/lib/apt/lists/*

# 4. 优化缓存：先只复制依赖清单，安装依赖
COPY requirements.txt .
# 这里的 pip 最好也指定一下国内源，双重保险
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 5. 复制剩余的所有代码文件
COPY . .

# 6. 赋予启动脚本执行权限
RUN chmod +x start.sh

# 7. 暴露端口
EXPOSE 8000 8501

# 8. 启动命令
CMD ["./start.sh"]