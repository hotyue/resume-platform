import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 确保 backend 目录在 path 里
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, DATABASE_URL, connect_args

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 动态设置 URL（跟随环境变量）
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# 关联所有 models
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connect_args_copy = {}
    if "sqlite" in DATABASE_URL:
        connect_args_copy["check_same_thread"] = False
    engine = create_engine(DATABASE_URL, connect_args=connect_args_copy, poolclass=pool.NullPool)

    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
