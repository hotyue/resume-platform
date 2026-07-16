"""seed system config

Revision ID: de7de95fa9d4
Revises: 158f392e0842
Create Date: 2026-07-15 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'de7de95fa9d4'
down_revision: Union[str, None] = '158f392e0842'
branch_labels: Union[tuple[str, ...], None] = None
depends_on: Union[tuple[str, ...], None] = None


# 系统配置种子数据 — 与前端 configItems 一一对应
SEED_CONFIGS = [
    ('custom_price',           19.99, '定制价格 (¥)'),
    ('delivery_hours',         24.0,  '交付周期 (小时)'),
    ('auto_accept_hours',      168.0, '自动验收 (小时) — 7 天'),
    ('penalty_hours',          8.0,   '违约金触发 (小时)'),
    ('penalty_rate',           10.0,  '违约金比例 (%)'),
    ('penalty_max',            50.0,  '违约金上限 (¥)'),
    ('consecutive_fail_limit', 3.0,   '连续超时限制次数'),
    ('min_withdraw',           50.0,  '最低提现 (¥)'),
    ('deposit_threshold',      20.0,  '保证金门槛 (¥)'),
]


def upgrade() -> None:
    """UPSERT 所有系统配置项（存在则跳过，不存在则插入）"""
    conn = op.get_bind()

    for key, value, desc in SEED_CONFIGS:
        # PostgreSQL: INSERT ... ON CONFLICT DO NOTHING
        conn.execute(text("""
            INSERT INTO system_config (key, value, description)
            VALUES (:key, :value, :description)
            ON CONFLICT (key) DO NOTHING
        """), {
            'key': key,
            'value': value,
            'description': desc,
        })


def downgrade() -> None:
    """回滚：删除种子数据（不删手动添加的配置项）"""
    conn = op.get_bind()
    keys = [key for key, _, _ in SEED_CONFIGS]
    conn.execute(text("""
        DELETE FROM system_config WHERE key IN :keys
    """), {'keys': tuple(keys)})
