"""管理员路由 — applications / orders / withdrawals / commission-config / config / refunds / users / audit-logs / dashboard / stats / release-frozen"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models as m
from auth import require_admin

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ================= Helpers =================

def _get_config(db: Session, key: str, default: float = 0.0) -> float:
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key).first()
    if cfg:
        return cfg.value
    return default


def _load_all_configs(db: Session) -> dict:
    configs = {}
    for c in db.query(m.SystemConfig).all():
        configs[c.key] = c.value
    defaults = {
        "download_price": 1.99,
        "custom_price": 19.99,
        "creator_rate": 0.30,
        "level1_rate": 0.15,
        "level2_rate": 0.08,
        "level3_rate": 0.05,
        "deposit_amount": 20.0,
        "auto_accept_hours": 168,
    }
    for k, v in defaults.items():
        if k not in configs:
            cfg = m.SystemConfig(key=k, value=v, description=k)
            db.add(cfg)
            db.commit()
            configs[k] = v
    return configs


# ================= Schemas =================

class ReviewApplyReq:
    pass


class ReviewWithdrawReq:
    pass


class UpdateUserReq:
    pass


class UpdateCommissionConfigReq:
    pass


class UpdateSystemConfigReq:
    pass


class ReviewRefundReq:
    pass


# ================= 入驻审核 =================

@router.get("/applications")
async def list_applications(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员查看入驻申请列表"""
    query = db.query(m.CreatorApplication, m.User).join(m.User)
    if status:
        query = query.filter(m.CreatorApplication.status == status)
    results = query.order_by(m.CreatorApplication.created_at.desc()).all()
    return [{
        "id": a.id, "user_id": a.user_id, "username": u.username,
        "real_name": a.real_name, "phone": a.phone, "wechat": a.wechat,
        "specialty": a.specialty, "portfolio_desc": a.portfolio_desc,
        "experience": a.experience, "status": a.status,
        "review_remark": a.review_remark,
        "created_at": str(a.created_at),
        "reviewed_at": str(a.reviewed_at) if a.reviewed_at else None,
    } for a, u in results]


@router.post("/applications/review")
async def review_application(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员审核入驻申请"""
    application_id = req_body.get("application_id")
    status = req_body.get("status")
    remark = req_body.get("remark", "")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    a = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.id == application_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="申请不存在")
    if a.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请已处理（当前状态: {a.status}）")

    a.status = status
    a.review_remark = remark
    a.reviewed_at = datetime.now()

    if status == "approved":
        user = db.query(m.User).filter(m.User.id == a.user_id).first()
        if user:
            # 解冻保证金
            user.deposit_frozen = 0.0
    db.commit()
    return {"id": a.id, "status": a.status, "message": "审核完成"}


# ================= 订单管理 =================

@router.get("/orders")
async def admin_orders(
    status: Optional[str] = Query(None, description="按状态筛选"),
    search: Optional[str] = Query(None, description="搜索订单号/模板名"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员订单列表"""
    query = db.query(m.Order, m.Template, m.User).outerjoin(
        m.Template, m.Order.template_id == m.Template.id
    ).outerjoin(
        m.User, m.Order.user_id == m.User.id
    )
    if status:
        query = query.filter(m.Order.status == status)
    if search:
        query = query.filter(
            m.Order.order_no.ilike(f"%{search}%") |
            m.Template.name.ilike(f"%{search}%")
        )
    total = query.count()
    results = query.order_by(m.Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "orders": [{
            "id": o.id, "order_no": o.order_no, "amount": o.amount,
            "status": o.status, "order_type": o.order_type,
            "template_name": t.name if t else "N/A",
            "template_category": t.category if t else "N/A",
            "user_name": u.username if u else "N/A",
            "creator_id": o.creator_id,
            "ref_user_id": o.ref_user_id,
            "created_at": str(o.created_at),
        } for o, t, u in results],
    }


@router.get("/orders/{order_no}")
async def admin_order_detail(
    order_no: str,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """订单详情"""
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    template = db.query(m.Template).filter(m.Template.id == order.template_id).first()
    user = db.query(m.User).filter(m.User.id == order.user_id).first()
    creator = db.query(m.User).filter(m.User.id == order.creator_id).first() if order.creator_id else None
    ref_user = db.query(m.User).filter(m.User.id == order.ref_user_id).first() if order.ref_user_id else None
    commissions = db.query(m.CommissionRecord).filter(
        m.CommissionRecord.order_no == order_no
    ).all()
    return {
        "order": {
            "id": order.id, "order_no": order.order_no, "amount": order.amount,
            "status": order.status, "order_type": order.order_type,
            "custom_requirements": order.custom_requirements,
            "created_at": str(order.created_at),
            "template": {"id": template.id, "name": template.name, "category": template.category} if template else None,
            "user": {"id": user.id, "username": user.username, "role": user.role} if user else None,
            "creator": {"id": creator.id, "username": creator.username} if creator else None,
            "ref_user": {"id": ref_user.id, "username": ref_user.username} if ref_user else None,
        },
        "commissions": [{
            "id": c.id, "user_id": c.user_id, "level": c.level,
            "amount": c.amount, "rate": c.rate,
        } for c in commissions],
    }


# ================= 提现管理 =================

@router.get("/withdrawals")
async def admin_withdrawals(
    status: Optional[str] = Query(None, description="pending/approved/rejected"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """提现列表"""
    query = db.query(m.WithdrawRequest, m.User).join(m.User)
    if status:
        query = query.filter(m.WithdrawRequest.status == status)
    total = query.count()
    results = query.order_by(m.WithdrawRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "withdrawals": [{
            "id": w.id, "user_id": w.user_id, "username": u.username,
            "amount": w.amount, "payment_info": w.payment_info,
            "status": w.status, "admin_remark": w.admin_remark,
            "created_at": str(w.created_at),
            "reviewed_at": str(w.reviewed_at) if w.reviewed_at else None,
        } for w, u in results],
    }


@router.post("/withdrawals/review")
async def review_withdraw(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """审核提现"""
    request_id = req_body.get("request_id")
    status = req_body.get("status")
    remark = req_body.get("remark", "")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    w = db.query(m.WithdrawRequest).filter(m.WithdrawRequest.id == request_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != "pending":
        raise HTTPException(status_code=400, detail=f"已处理（当前: {w.status}）")

    w.status = status
    w.admin_remark = remark
    w.reviewed_at = datetime.now()

    if status == "approved":
        # 方案C：批准时扣减余额 + 解冻
        user = db.query(m.User).filter(m.User.id == w.user_id).first()
        if user:
            user.wallet_balance -= w.amount
            user.frozen_withdraw = max(0, (user.frozen_withdraw or 0) - w.amount)
            user.total_withdrawn = (user.total_withdrawn or 0) + w.amount
    elif status == "rejected":
        # 拒绝时解冻
        user = db.query(m.User).filter(m.User.id == w.user_id).first()
        if user:
            user.frozen_withdraw = max(0, (user.frozen_withdraw or 0) - w.amount)

    db.commit()
    return {"id": w.id, "status": w.status, "message": "审核完成"}


# ================= 分佣配置 =================

@router.get("/commission-config")
async def get_commission_config(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """获取当前分佣比例"""
    configs = db.query(m.CommissionConfig).order_by(m.CommissionConfig.level).all()
    return {
        "level_1_rate": configs[0].rate if len(configs) > 0 else 0.15,
        "level_2_rate": configs[1].rate if len(configs) > 1 else 0.08,
        "level_3_rate": configs[2].rate if len(configs) > 2 else 0.05,
    }


@router.put("/commission-config")
async def update_commission_config(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """修改分佣比例"""
    level = req_body.get("level")
    rate = req_body.get("rate")
    if level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="级别必须是 1/2/3")
    if not (0 <= rate <= 1):
        raise HTTPException(status_code=400, detail="比例必须在 0~1 之间")
    config = db.query(m.CommissionConfig).filter(m.CommissionConfig.level == level).first()
    if not config:
        config = m.CommissionConfig(level=level, rate=rate)
        db.add(config)
    else:
        config.rate = rate
        config.updated_at = datetime.now()
    db.commit()
    return {"level": level, "rate": rate, "message": f"第{level}级分佣比例已更新为 {rate*100:.0f}%"}


# ================= 系统配置 =================

@router.get("/config")
async def get_system_config(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """获取系统配置"""
    return _load_all_configs(db)


@router.put("/config")
async def update_system_config(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """更新系统配置"""
    valid_keys = ["download_price", "custom_price", "creator_rate",
                  "level1_rate", "level2_rate", "level3_rate", "deposit_amount",
                  "auto_accept_hours"]
    key = req_body.get("key", "")
    value = req_body.get("value")
    if key not in valid_keys:
        raise HTTPException(status_code=400, detail=f"无效的配置项: {key}")
    if key == "auto_accept_hours":
        if not (24 <= value <= 720):
            raise HTTPException(status_code=400, detail="自动验收时长必须在 24-720 小时之间")
    elif value < 0:
        raise HTTPException(status_code=400, detail="配置值不能为负数")
    cfg = db.query(m.SystemConfig).filter(m.SystemConfig.key == key).first()
    if not cfg:
        cfg = m.SystemConfig(key=key, value=value)
        db.add(cfg)
    else:
        cfg.value = value
        cfg.updated_at = datetime.now()
    db.commit()
    return {"key": key, "value": value, "message": "配置已更新"}


# 公开配置（无需认证 — 前端展示用）
@router.get("/config/public")
async def get_public_config(db: Session = Depends(get_db)):
    """返回前端需要展示的公开配置项"""
    return {
        "creator_rate": _get_config(db, "creator_rate", 0.30),
        "deposit_amount": _get_config(db, "deposit_amount", 20.0),
    }


# ================= 退款审核 =================

@router.get("/refunds")
async def admin_refunds(
    status: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    query = db.query(m.RefundRequest)
    if status:
        query = query.filter(m.RefundRequest.status == status)
    total = query.count()
    results = query.order_by(m.RefundRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for r in results:
        buyer = db.query(m.User).filter(m.User.id == r.buyer_id).first()
        creator = db.query(m.User).filter(m.User.id == r.creator_id).first() if r.creator_id else None
        items.append({
            "id": r.id, "order_no": r.order_no,
            "buyer": buyer.username if buyer else "未知",
            "creator": creator.username if creator else "无",
            "refund_amount": r.refund_amount, "creator_deduction": r.creator_deduction,
            "reason": r.reason, "status": r.status, "created_at": str(r.created_at)
        })
    return {"total": total, "page": page, "page_size": page_size, "refunds": items}


@router.post("/refunds/review")
async def review_refund(
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    refund_id = req_body.get("refund_id")
    status = req_body.get("status")
    remark = req_body.get("remark", "")
    if status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    r = db.query(m.RefundRequest).filter(m.RefundRequest.id == refund_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="退款申请不存在")
    if r.status != "pending":
        raise HTTPException(status_code=400, detail="已处理")
    r.status = status
    r.admin_remark = remark
    r.reviewed_at = datetime.now()
    if status == "approved":
        order = db.query(m.Order).filter(m.Order.order_no == r.order_no).first()
        buyer = db.query(m.User).filter(m.User.id == r.buyer_id).first()
        if order:
            order.status = "refunded"
        if buyer:
            buyer.wallet_balance += r.refund_amount
        if r.creator_id:
            creator = db.query(m.User).filter(m.User.id == r.creator_id).first()
            if creator:
                creator.wallet_balance -= r.creator_deduction
    db.commit()
    return {"id": r.id, "status": r.status}


# ================= 用户管理 =================

@router.get("/users")
async def admin_users(
    search: Optional[str] = Query(None, description="搜索用户名"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """用户列表"""
    query = db.query(m.User)
    if search:
        query = query.filter(m.User.username.ilike(f"%{search}%"))
    if role:
        query = query.filter(m.User.role == role)
    total = query.count()
    results = query.order_by(m.User.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "users": [{
            "id": u.id, "username": u.username, "role": u.role,
            "wallet_balance": round(u.wallet_balance, 2),
            "deposit_frozen": round(u.deposit_frozen, 2),
            "team_size": u.team_size, "parent_id": u.parent_id,
            "created_at": str(u.created_at) if u.created_at else "N/A",
        } for u in results],
    }


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: int,
    req_body: dict,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """修改用户角色/调整余额"""
    user = db.query(m.User).filter(m.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req_body.get("role") and req_body["role"] in ("user", "admin"):
        user.role = req_body["role"]
    if req_body.get("wallet_balance") is not None and req_body["wallet_balance"] >= 0:
        user.wallet_balance = req_body["wallet_balance"]
    db.commit()
    return {"id": user.id, "role": user.role, "wallet_balance": round(user.wallet_balance, 2)}


# ================= 审计日志 =================

@router.get("/audit-logs")
async def admin_audit_logs(
    user_id: Optional[int] = Query(None),
    order_no: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    query = db.query(m.CreatorAuditLog)
    if user_id:
        query = query.filter(m.CreatorAuditLog.user_id == user_id)
    if order_no:
        query = query.filter(m.CreatorAuditLog.order_no == order_no)
    if action:
        query = query.filter(m.CreatorAuditLog.action == action)
    total = query.count()
    logs = query.order_by(m.CreatorAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "logs": [{
            "id": log.id, "user_id": log.user_id, "order_no": log.order_no,
            "action": log.action, "detail": log.detail,
            "penalty_amount": log.penalty_amount,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log in logs],
        "total": total,
    }


# ================= 数据看板 =================

@router.get("/dashboard")
async def admin_dashboard(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    paid_statuses = ["paid", "processing", "completed", "accepted", "in_progress", "delivered", "awaiting_claim"]
    total_users = db.query(m.User).count()
    total_orders = db.query(m.Order).count()
    total_revenue = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
        m.Order.status.in_(paid_statuses)).scalar()) or 0.0
    today_orders = db.query(m.Order).filter(m.Order.created_at >= today_start).count()
    today_revenue = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
        m.Order.created_at >= today_start, m.Order.status.in_(paid_statuses)).scalar()) or 0.0
    month_orders = db.query(m.Order).filter(m.Order.created_at >= month_start).count()
    month_revenue = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
        m.Order.created_at >= month_start, m.Order.status.in_(paid_statuses)).scalar()) or 0.0
    total_commission = (db.query(func.coalesce(func.sum(m.CommissionRecord.amount), 0)).scalar()) or 0.0
    pending_orders = db.query(m.Order).filter(m.Order.status == "pending").count()
    pending_withdrawals = db.query(m.WithdrawRequest).filter(m.WithdrawRequest.status == "pending").count()
    pending_apps = db.query(m.CreatorApplication).filter(m.CreatorApplication.status == "pending").count()
    pending_refunds = db.query(m.RefundRequest).filter(m.RefundRequest.status == "pending").count()
    role_stats = {r: db.query(m.User).filter(m.User.role == r).count() for r in ["user", "admin"]}
    role_stats["creator"] = db.query(m.CreatorApplication).filter(
        m.CreatorApplication.status == "approved"
    ).count()
    role_stats["promoter"] = db.query(m.User).filter(m.User.team_size > 0).count()
    status_stats = {s: db.query(m.Order).filter(m.Order.status == s).count() for s in
                    ["pending", "paid", "awaiting_claim", "in_progress", "delivered", "accepted", "refunded"]}
    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        nd = day + timedelta(days=1)
        count = db.query(m.Order).filter(m.Order.created_at >= day, m.Order.created_at < nd).count()
        rev = (db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
            m.Order.created_at >= day, m.Order.created_at < nd, m.Order.status.in_(paid_statuses)).scalar()) or 0.0
        trend.append({"date": day.strftime("%m-%d"), "orders": count, "revenue": round(rev, 2)})
    return {
        "total_users": total_users, "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2), "today_orders": today_orders,
        "today_revenue": round(today_revenue, 2), "month_orders": month_orders,
        "month_revenue": round(month_revenue, 2), "total_commission_paid": round(total_commission, 2),
        "pending_orders": pending_orders, "pending_withdrawals": pending_withdrawals,
        "pending_applications": pending_apps, "pending_refunds": pending_refunds,
        "role_stats": role_stats, "order_status_stats": status_stats, "daily_trend": trend,
    }


@router.get("/stats")
async def admin_stats(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理后台数据概览（兼容旧版）"""
    paid_statuses = ["paid", "processing", "completed", "accepted", "in_progress", "delivered", "awaiting_claim"]
    return {
        "total_users": db.query(m.User).count(),
        "creator_count": db.query(m.CreatorApplication).filter(
            m.CreatorApplication.status == "approved"
        ).count(),
        "promoter_count": db.query(m.User).filter(m.User.team_size > 0).count(),
        "pending_approvals": db.query(m.CreatorApplication).filter(
            m.CreatorApplication.status == "pending"
        ).count(),
        "total_revenue": round((db.query(func.coalesce(func.sum(m.Order.amount), 0)).filter(
            m.Order.status.in_(paid_statuses)).scalar()) or 0.0, 2),
        "total_commission": round((db.query(func.coalesce(func.sum(m.CommissionRecord.amount), 0)).scalar()) or 0.0, 2),
        "pending_withdrawals": db.query(m.WithdrawRequest).filter(
            m.WithdrawRequest.status == "pending"
        ).count(),
    }


# ================= 冻结佣金释放 =================

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
        # 释放冻结佣金（settle_custom_commission 在 commission.py 中）
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
