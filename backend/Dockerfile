FROM python:3.11-slim

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 【核心资产封装】：将宿主机预先拉取的素材库拷贝到容器内挂载点
COPY assets_source /app/assets/ResumeCollection

# 暴露端口并启动服务
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
