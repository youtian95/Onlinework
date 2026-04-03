# 使用官方 Python 轻量级镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量 (防止 Python 生成 .pyc 文件，防止缓冲)
ENV PyTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 复制依赖文件
COPY backend/requirements.txt ./backend/
COPY packages/civil-toolkit/ ./packages/civil-toolkit/

# 安装依赖
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -e ./packages/civil-toolkit

# 复制后端代码
# 注意：假设构建上下文是项目根目录，所以复制 backend 文件夹
COPY backend/ ./backend/
# 复制可能的 .env 文件 (或者在 docker-compose 中配置环境变量)
COPY .env.secret .

# 创建必要的目录
RUN mkdir -p backend/public backend/problems backend/db backend/archive

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
