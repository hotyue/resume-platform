"""管理员路由 — 系统配置"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()

# 配置默认值回退
DEFAULT_CONFIGS = {
    "download_price": 1.99,
    "custom_price": 19.99,
    "creator_rate": 0.30,
    "level1_rate": 0.30,
    "level2_rate": 0.10,
    "level3_rate": 0.05,
    "deposit_amount": 20.0,
    "auto_accept_hours": 168.0,
    "delivery_hours": 24.0,
    "penalty_hours": 8.0,
    "penalty_rate": 10.0,
    "penalty_max": 50.0,
    "consecutive_fail_limit": 3.0,
    "min_withdraw": 50.0,
    "deposit_threshold": 20.0,
}


def load_all_configs(db: Session) -> dict:
    """加载系统配置，缺失项使用默认值回退"""
    configs = db.query(m.SystemConfig).all()
    result = {c.key: c.value for c in configs}
    for key, default in DEFAULT_CONFIGS.items():
        if key not in result:
            result[key] = default
    return result


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """获取系统配置"""
    return load_all_configs(db)


VALID_KEYS = list(DEFAULT_CONFIGS.keys())


@router.put("/config")
async def update_config(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """更新系统配置"""
    key = req_body.get("key")
    value = req_body.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="缺少配置键")
    if key not in VALID_KEYS:
        raise HTTPException(status_code=400, detail=f"无效的配置项: {key}")

    # 值范围校验
    if key == "auto_accept_hours" and not (24 <= float(value) <= 720):
        raise HTTPException(status_code=400, detail="自动验收时长必须在 24-720 小时之间")
    if value is not None and float(value) < 0:
        raise HTTPException(status_code=400, detail="配置值不能为负数")

    config = db.query(m.SystemConfig).filter(m.SystemConfig.key == key).first()
    if not config:
        config = m.SystemConfig(key=key, value=value)
        db.add(config)
    else:
        config.value = value
        config.updated_at = datetime.now()

    db.commit()
    return {"key": key, "value": value, "message": "配置已更新"}
