import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 优先使用环境变量中的数据库连接串，否则使用 SQLite 本地开发
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./resume_dev.db"
)

# SQLite 需要 check_same_thread=False
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()