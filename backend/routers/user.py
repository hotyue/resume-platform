"""用户路由 — me / profile / password / recharge / wallet / withdraw / team / commission-history / stats"""
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models as m
from auth import get_current_user

router = APIRouter(prefix="/api/v1/user", tags=["user"])


# ================= Helpers =================

def _get_config(db: Session, key: str, default: float = 0.0) -> float:
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key).first()
    if cfg:
        return cfg.value
    descriptions = {
        "download_price": "下载订单金额", "custom_price": "定制订单金额",
        "creator_rate": "制作者分佣比例", "level1_rate": "一级推广分佣比例",
        "level2_rate": "二级推广分佣比例", "level3_rate": "三级推广分佣比例(已停用)",
        "deposit_amount": "制作者保证金金额",
    }
    cfg = m.SystemConfig(key=key, value=default, description=descriptions.get(key, key))
    db.add(cfg)
    db.commit()
    return default


def _get_deposit_amount(db: Session) -> float:
    return _get_config(db, "deposit_amount", 20.0)


def _build_roles(user: m.User, db: Session) -> list:
    roles = [user.role]
    if db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == user.id,
        m.CreatorApplication.status == "approved"
    ).first():
        roles.append("creator")
    if (user.team_size or 0) > 0:
        roles.append("promoter")
    return roles


# ================= Schemas =================

class UpdateProfileReq:
    pass  # imported from schemas if needed, inline for now


# ================= Endpoints =================

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户完整信息（含钱包、邀请等）"""
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    invite_code = f"INV{user.id:06d}"
    invite_url = f"{os.getenv('APP_BASE_URL', 'http://localhost:5173')}/?ref={invite_code}"
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "roles": _build_roles(user, db),
        "wallet_balance": round(user.wallet_balance or 0, 2),
        "deposit_frozen": round(user.deposit_frozen or 0, 2),
        "frozen_withdraw": round(user.frozen_withdraw or 0, 2),
        "available_balance": round(user.available_balance, 2),
        "invite_code": invite_code,
        "invite_url": invite_url,
        "alipay_account": user.alipay_account,
        "wechat_account": user.wechat_account,
        "total_withdrawn": round(user.total_withdrawn or 0, 2),
        "total_commission": round((user.referral_commission or 0) + (user.making_commission or 0), 2),
        "team_size": user.team_size or 0,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.put("/profile")
async def update_profile(req_body: dict, db: Session = Depends(get_db),
                         current_user: dict = Depends(get_current_user)):
    """更新用户资料"""
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    alipay_account = req_body.get("alipay_account")
    wechat_account = req_body.get("wechat_account")
    if alipay_account is not None:
        user.alipay_account = alipay_account
    if wechat_account is not None:
        user.wechat_account = wechat_account
    db.commit()
    return {"message": "资料已更新"}


@router.put("/password")
async def update_password(req_body: dict, db: Session = Depends(get_db),
                          current_user: dict = Depends(get_current_user)):
    """更新密码"""
    from auth import verify_password, hash_password
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if not verify_password(req_body.get("old_password", ""), user.password_hash or ""):
        raise HTTPException(status_code=400, detail="旧密码错误")
    user.password_hash = hash_password(req_body["new_password"])
    db.commit()
    return {"message": "密码已更新"}


@router.post("/recharge")
async def recharge(req_body: dict, db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user)):
    """充值"""
    amount = req_body.get("amount", 0)
    method = req_body.get("method", "manual")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于0")
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    user.wallet_balance += amount
    db.add(m.RechargeRecord(user_id=user.id, amount=amount, method=method, status="completed"))
    db.commit()
    return {"message": "充值成功", "amount": amount, "wallet_balance": round(user.wallet_balance, 2)}


@router.get("/wallet")
async def get_wallet(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """获取钱包信息"""
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    return {
        "wallet_balance": round(user.wallet_balance or 0, 2),
        "deposit_frozen": round(user.deposit_frozen or 0, 2),
        "available_balance": round(user.available_balance, 2),
        "deposit_amount": round(_get_deposit_amount(db), 2),
        "total_withdrawn": round(user.total_withdrawn or 0, 2),
    }


@router.post("/withdraw")
async def withdraw(req_body: dict, db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user)):
    """提交提现申请"""
    amount = req_body.get("amount", 0)
    payment_info = req_body.get("payment_info", "")
    account_type = req_body.get("account_type", "alipay")
    user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
    if amount <= 0:
        raise HTTPException(status_code=400, detail="提现金额必须大于0")
    if user.available_balance < amount:
        raise HTTPException(status_code=400, detail=f"可提现余额不足（当前: {round(user.available_balance, 2)}）")
    w = m.WithdrawRequest(user_id=user.id, amount=amount,
                          payment_info=payment_info, account_type=account_type)
    db.add(w)
    # 方案C：申请时冻结，不扣余额
    user.frozen_withdraw = (user.frozen_withdraw or 0.0) + amount
    db.commit()
    return {"id": w.id, "amount": amount, "status": "pending"}


@router.get("/team")
async def get_team(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    quarter: Optional[str] = Query(None),
):
    """获取用户团队信息（1/2/3 级）

    quarter 格式: 2026-Q1 / 2026-Q2 / 2026-Q3 / 2026-Q4
    不传则显示全部（仍限制每级 TOP5）
    每级按贡献值（当季佣金总额）降序排列，最多 5 名
    """
    uid = current_user["id"]
    user = db.query(m.User).filter(m.User.id == uid).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    # 解析季度范围
    quarter_start = None
    quarter_end = None
    if quarter:
        try:
            year, q = quarter.split("-Q")
            year = int(year)
            q = int(q)
            month = (q - 1) * 3 + 1
            quarter_start = datetime(year, month, 1)
            if q == 4:
                quarter_end = datetime(year + 1, 1, 1)
            else:
                quarter_end = datetime(year, month + 3, 1)
        except (ValueError, IndexError):
            pass

    def user_contrib(user_id: int) -> float:
        q = db.query(func.sum(m.CommissionRecord.amount)).filter(
            m.CommissionRecord.user_id == user_id
        )
        if quarter_start:
            q = q.filter(m.CommissionRecord.created_at >= quarter_start)
        if quarter_end:
            q = q.filter(m.CommissionRecord.created_at < quarter_end)
        return q.scalar() or 0.0

    def build_member(u: m.User) -> dict:
        member_roles = ["user"]
        if db.query(m.CreatorApplication).filter(
            m.CreatorApplication.user_id == u.id,
            m.CreatorApplication.status == "approved"
        ).first():
            member_roles.append("creator")
        if (u.team_size or 0) > 0:
            member_roles.append("promoter")
        return {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "roles": member_roles,
            "wallet_balance": u.wallet_balance,
            "contribution": round(user_contrib(u.id), 2),
        }

    # 0 级（自己）
    self_roles = ["user"]
    if db.query(m.CreatorApplication).filter(
        m.CreatorApplication.user_id == user.id,
        m.CreatorApplication.status == "approved"
    ).first():
        self_roles.append("creator")
    if (user.team_size or 0) > 0:
        self_roles.append("promoter")
    level_0 = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "roles": self_roles,
        "wallet_balance": user.wallet_balance,
        "contribution": round(user_contrib(user.id), 2),
    }

    # 1 级（直接下级）— 按贡献值 TOP5
    l1 = db.query(m.User).filter(m.User.parent_id == uid).all()
    level_1 = sorted([build_member(u) for u in l1], key=lambda x: x["contribution"], reverse=True)[:5]
    l1_ids = {u.id for u in l1}

    # 2 级 — 按贡献值 TOP5
    level_2 = []
    if l1_ids:
        l2 = db.query(m.User).filter(m.User.parent_id.in_(l1_ids)).all()
        level_2 = sorted([build_member(u) for u in l2], key=lambda x: x["contribution"], reverse=True)[:5]
        l2_ids = {u.id for u in l2}
    else:
        l2_ids = set()

    # 3 级 — 按贡献值 TOP5
    level_3 = []
    if l2_ids:
        l3 = db.query(m.User).filter(m.User.parent_id.in_(l2_ids)).all()
        level_3 = sorted([build_member(u) for u in l3], key=lambda x: x["contribution"], reverse=True)[:5]

    # 总人数（不受 TOP5 限制）
    total_l1 = len(l1)
    total_l2 = len(db.query(m.User).filter(m.User.parent_id.in_(l1_ids)).all()) if l1_ids else 0
    total_l3 = len(db.query(m.User).filter(m.User.parent_id.in_(l2_ids)).all()) if l2_ids else 0

    return {
        "level_0": level_0,
        "level_1": level_1,
        "level_2": level_2,
        "level_3": level_3,
        "total_l1": total_l1,
        "total_l2": total_l2,
        "total_l3": total_l3,
        "quarter": quarter,
    }


@router.get("/commission-history")
async def get_commission_history(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户佣金明细（关联订单信息）"""
    uid = current_user["id"]
    records = db.query(m.CommissionRecord).filter(
        m.CommissionRecord.user_id == uid
    ).order_by(m.CommissionRecord.created_at.desc()).all()
    result = []
    for r in records:
        order = db.query(m.Order).filter(m.Order.order_no == r.order_no).first()
        if not order:
            continue

        buyer = db.query(m.User).filter(m.User.id == order.user_id).first()
        buyer_name = buyer.username if buyer else "未知"

        creator_name = ""
        if order.creator_id:
            creator = db.query(m.User).filter(m.User.id == order.creator_id).first()
            creator_name = creator.username if creator else "未知"

        template_name = ""
        if order.template_id:
            template = db.query(m.Template).filter(m.Template.id == order.template_id).first()
            template_name = template.name if template else ""

        item = {
            "id": r.id,
            "order_no": r.order_no,
            "level": r.level,
            "amount": r.amount,
            "rate": r.rate,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "buyer_name": buyer_name,
            "creator_name": creator_name,
            "template_name": template_name,
            "order_type": order.order_type,
            "order_amount": order.amount,
            "order_status": order.status,
            "ordered_at": order.created_at.isoformat() if order.created_at else None,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
            "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
        }
        result.append(item)
    return result


@router.get("/stats/{user_id}")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """获取用户统计信息"""
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    total_commission = db.query(func.sum(m.CommissionRecord.amount)).filter(
        m.CommissionRecord.user_id == user_id
    ).scalar() or 0.0
    team_count = db.query(m.User).filter(m.User.parent_id == user_id).count()
    order_count = db.query(m.Order).filter(m.Order.user_id == user_id).count()

    return {
        "user_id": user_id,
        "total_commission": total_commission,
        "referral_commission": round(user.referral_commission, 2),
        "making_commission": round(user.making_commission, 2),
        "team_count": team_count,
        "order_count": order_count,
    }
