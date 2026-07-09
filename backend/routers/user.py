"""用户路由：注册、资料、团队、佣金历史、提现"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
import models
from commission import resolve_ref_parent, update_parent_team_sizes
from schemas import RegisterReq, WithdrawReq

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.post("/register")
async def register(req: RegisterReq, db: Session = Depends(get_db)):
    """兼容旧版注册（无密码，仅用于测试）"""
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    parent_id = resolve_ref_parent(req.ref_code, db)

    new_user = models.User(username=req.username, role="user", parent_id=parent_id)
    db.add(new_user)
    db.flush()

    if parent_id:
        update_parent_team_sizes(parent_id, db)

    db.commit()
    return {"id": new_user.id, "username": new_user.username, "parent_id": parent_id}


@router.get("/profile")
async def get_user_profile(db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == 2).first()
    invite_code = f"INVITE_{user.id}"
    return {
        "id": user.id, "username": user.username, "role": user.role,
        "wallet_balance": round(user.wallet_balance, 2),
        "team_size": user.team_size,
        "invite_code": invite_code,
        "invite_url": f"https://resume.example.com/register?ref={invite_code}",
    }


@router.get("/team")
async def get_team(db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == 2).first()
    children = db.query(models.User).filter(models.User.parent_id == 2).all()
    grandchildren = []
    for child in children:
        gcs = db.query(models.User).filter(models.User.parent_id == child.id).all()
        for gc in gcs:
            grandchildren.append(gc)
    great_grandchildren = []
    for gc in grandchildren:
        ggcs = db.query(models.User).filter(models.User.parent_id == gc.id).all()
        for ggc in ggcs:
            great_grandchildren.append(ggc)

    def user_info(u):
        return {"id": u.id, "username": u.username, "role": u.role, "wallet_balance": round(u.wallet_balance, 2)}

    return {
        "level_0": user_info(user),
        "level_1": [user_info(c) for c in children],
        "level_2": [user_info(gc) for gc in grandchildren],
        "level_3": [user_info(ggc) for ggc in great_grandchildren],
    }


@router.get("/commission-history")
async def get_commission_history(limit: int = 20, db: Session = Depends(get_db)):
    records = (
        db.query(models.CommissionRecord)
        .filter(models.CommissionRecord.user_id == 2)
        .order_by(models.CommissionRecord.created_at.desc())
        .limit(limit).all()
    )
    return [{
        "id": r.id, "order_no": r.order_no, "level": r.level,
        "amount": r.amount, "rate": r.rate, "created_at": str(r.created_at),
    } for r in records]


@router.get("/stats/{user_id}")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    total_commission = (
        db.query(models.CommissionRecord)
        .filter(models.CommissionRecord.user_id == user_id)
        .with_entities(models.CommissionRecord.amount, models.CommissionRecord.level).all()
    )
    by_level = {1: 0, 2: 0, 3: 0}
    total = 0
    for amt, lv in total_commission:
        by_level[lv] = round(by_level[lv] + amt, 2)
        total += amt
    direct_count = db.query(models.User).filter(models.User.parent_id == user_id).count()
    return {
        "user_id": user_id, "username": user.username, "role": user.role,
        "wallet_balance": round(user.wallet_balance, 2),
        "team_size": user.team_size, "direct_count": direct_count,
        "total_commission": round(total, 2), "commission_by_level": by_level,
    }


@router.post("/withdraw")
async def submit_withdraw(req: WithdrawReq, db: Session = Depends(get_db)):
    """用户提交提现申请"""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.amount < 50:
        raise HTTPException(status_code=400, detail="最低提现金额为50元")
    if req.amount > user.wallet_balance:
        raise HTTPException(status_code=400, detail="余额不足")

    user.wallet_balance -= req.amount
    withdraw = models.WithdrawRequest(
        user_id=req.user_id, amount=req.amount, payment_info=req.payment_info, status="pending"
    )
    db.add(withdraw)
    db.commit()
    return {"id": withdraw.id, "status": "pending", "message": "提现申请已提交，等待管理员审核"}
