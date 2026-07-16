FROM python:3.11-slim

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# Alembic 迁移配置
COPY backend/alembic.ini .
COPY backend/alembic/ alembic/

# 【核心资产封装】：模板素材库通过 volume mount 挂载，不打包进镜像
RUN mkdir -p /app/assets

# 启动入口：先执行数据库迁移，再启动服务
RUN chmod +x /app/entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
