FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY pyproject.toml uv.lock ./

# 安装依赖（不安装 dev 组，生产环境只装主依赖）
RUN uv sync --frozen --no-dev --no-install-project

# 复制源码
COPY src/ ./src/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.websocket.server:app", "--host", "0.0.0.0", "--port", "8000"]
