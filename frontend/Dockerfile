# Stage 1: Build Frontend
FROM node:24-alpine AS builder

WORKDIR /app/frontend

# 复制依赖文件
COPY frontend/package*.json ./
# 安装依赖
RUN npm install

# 复制源代码
COPY frontend/ ./

# 复制外部引用的 docs 目录，使相对路径 `../../../docs/guide.md` 生效
COPY docs/ ../docs/

# 构建 (生成 dist 目录)
RUN npm run build

# Stage 2: Nginx Serve
FROM nginx:alpine

# 复制 Nginx 配置文件
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# 从 Stage 1 复制构建产物到 Nginx 目录
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
