"""管理员路由 — 冻结佣金释放"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


@router.post("/commission/release-frozen")
async def release_frozen_commissions(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """超时自动验收 + 释放冻结佣金"""
    now = datetime.now()
    auto_accept = db.query(m.Order).filter(
        m.Order.status == "delivered",
        m.Order.freeze_until <= now
    ).all()
    auto_count = 0
    for order in auto_accept:
        order.status = "accepted"
        order.accepted_at = now
        # 释放冻结佣金
        try:
            from commission import settle_custom_commission
            settle_custom_commission(order, db)
        except ImportError:
            # fallback: 手动释放冻结记录
            pending = db.query(m.CommissionPending).filter(
                m.CommissionPending.order_no == order.order_no,
                m.CommissionPending.status == "frozen"
            ).all()
            for p in pending:
                p.status = "released"
                user = db.query(m.User).filter(m.User.id == p.user_id).first()
                if user:
                    user.wallet_balance += p.amount
                    user.making_commission = (user.making_commission or 0) + p.amount
                db.add(m.CommissionRecord(
                    order_no=order.order_no, user_id=p.user_id,
                    role_type=p.role_type, amount=p.amount, rate=p.rate,
                ))
        auto_count += 1
    db.commit()
    return {
        "auto_accepted_orders": auto_count,
        "message": f"自动验收 {auto_count} 个订单，佣金已到账",
    }


# 分佣配置（兼容旧版）
@router.get("/commission-config")
async def get_commission_config(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """返回全量系统配置（兼容旧前端）"""
    from .config import load_all_configs
    return load_all_configs(db)


@router.put("/commission-config")
async def update_commission_config(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """更新分佣比例（兼容旧前端）"""
    level = req_body.get("level")
    rate = req_body.get("rate")
    if level not in (1, 2):
        raise HTTPException(status_code=400, detail="级别必须是 1/2")
    key_map = {1: "level1_rate", 2: "level2_rate"}  # level3已停用
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key_map[level]).first()
    if not cfg:
        cfg = m.SystemConfig(key=key_map[level], value=rate)
        db.add(cfg)
    else:
        cfg.value = rate
        cfg.updated_at = datetime.now()
    db.commit()
    return {"level": level, "rate": rate, "message": f"第{level}级分佣比例已更新为 {rate*100:.0f}%"}
