"""管理员路由：入驻审核、订单管理、提现审核、分佣配置、用户管理、数据看板"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timedelta

from database import get_db
import models
from auth import require_admin
from schemas import ReviewApplyReq, ReviewWithdrawReq, UpdateUserReq, UpdateCommissionConfigReq

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ================= 入驻审核 =================

@router.get("/applications")
async def list_applications(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员查看入驻申请列表"""
    query = db.query(models.CreatorApplication, models.User).join(models.User)
    if status:
        query = query.filter(models.CreatorApplication.status == status)
    results = query.order_by(models.CreatorApplication.created_at.desc()).all()

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
    req: ReviewApplyReq,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理员审核入驻申请"""
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")

    a = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.id == req.application_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="申请不存在")
    if a.status != "pending":
        raise HTTPException(status_code=400, detail=f"该申请已处理（当前状态: {a.status}）")

    a.status = req.status
    a.review_remark = req.remark
    a.reviewed_at = datetime.now()

    if req.status == "approved":
        user = db.query(models.User).filter(models.User.id == a.user_id).first()
        if user:
            user.role = "creator"

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
    query = db.query(models.Order, models.Template, models.User).outerjoin(
        models.Template, models.Order.template_id == models.Template.id
    ).outerjoin(
        models.User, models.Order.user_id == models.User.id
    )

    if status:
        query = query.filter(models.Order.status == status)
    if search:
        query = query.filter(
            models.Order.order_no.ilike(f"%{search}%") |
            models.Template.name.ilike(f"%{search}%")
        )

    total = query.count()
    results = (
        query.order_by(models.Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
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
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    template = db.query(models.Template).filter(models.Template.id == order.template_id).first()
    user = db.query(models.User).filter(models.User.id == order.user_id).first()
    creator = db.query(models.User).filter(models.User.id == order.creator_id).first() if order.creator_id else None
    ref_user = db.query(models.User).filter(models.User.id == order.ref_user_id).first() if order.ref_user_id else None

    commissions = db.query(models.CommissionRecord).filter(
        models.CommissionRecord.order_no == order_no
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
    query = db.query(models.WithdrawRequest, models.User).join(models.User)
    if status:
        query = query.filter(models.WithdrawRequest.status == status)

    total = query.count()
    results = (
        query.order_by(models.WithdrawRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

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
    req: ReviewWithdrawReq,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """审核提现"""
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")

    w = db.query(models.WithdrawRequest).filter(models.WithdrawRequest.id == req.request_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != "pending":
        raise HTTPException(status_code=400, detail=f"已处理（当前: {w.status}）")

    w.status = req.status
    w.admin_remark = req.remark
    w.reviewed_at = datetime.now()

    if req.status == "rejected":
        user = db.query(models.User).filter(models.User.id == w.user_id).first()
        if user:
            user.wallet_balance += w.amount

    db.commit()
    return {"id": w.id, "status": w.status, "message": "审核完成"}


# ================= 分佣配置 =================

@router.get("/commission-config")
async def get_commission_config(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """获取当前分佣比例"""
    configs = db.query(models.CommissionConfig).order_by(models.CommissionConfig.level).all()
    return {
        "level_1_rate": configs[0].rate if len(configs) > 0 else 0.15,
        "level_2_rate": configs[1].rate if len(configs) > 1 else 0.08,
        "level_3_rate": configs[2].rate if len(configs) > 2 else 0.05,
    }


@router.put("/commission-config")
async def update_commission_config(
    req: UpdateCommissionConfigReq,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """修改分佣比例"""
    if req.level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="级别必须是 1/2/3")
    if not (0 <= req.rate <= 1):
        raise HTTPException(status_code=400, detail="比例必须在 0~1 之间")

    config = db.query(models.CommissionConfig).filter(
        models.CommissionConfig.level == req.level
    ).first()
    if not config:
        config = models.CommissionConfig(level=req.level, rate=req.rate)
        db.add(config)
    else:
        config.rate = req.rate
        config.updated_at = datetime.now()

    db.commit()
    return {"level": req.level, "rate": req.rate, "message": f"第{req.level}级分佣比例已更新为 {req.rate*100:.0f}%"}


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
    query = db.query(models.User)
    if search:
        query = query.filter(models.User.username.ilike(f"%{search}%"))
    if role:
        query = query.filter(models.User.role == role)

    total = query.count()
    results = query.order_by(models.User.id).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total, "page": page, "page_size": page_size,
        "users": [{
            "id": u.id, "username": u.username, "role": u.role,
            "wallet_balance": round(u.wallet_balance, 2),
            "team_size": u.team_size, "parent_id": u.parent_id,
            "created_at": str(u.created_at) if hasattr(u, 'created_at') and u.created_at else "N/A",
        } for u in results],
    }


@router.put("/users/{user_id}")
async def admin_update_user(
    user_id: int,
    req: UpdateUserReq,
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """修改用户角色/调整余额"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if req.role and req.role in ("user", "promoter", "creator", "admin"):
        user.role = req.role
    if req.wallet_balance is not None and req.wallet_balance >= 0:
        user.wallet_balance = req.wallet_balance

    db.commit()
    return {"id": user.id, "role": user.role, "wallet_balance": round(user.wallet_balance, 2)}


# ================= 数据看板 =================

@router.get("/dashboard")
async def admin_dashboard(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """数据看板"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.query(models.User).count()
    total_orders = db.query(models.Order).count()
    total_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0

    today_orders = db.query(models.Order).filter(models.Order.created_at >= today_start).count()
    today_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.created_at >= today_start,
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_orders = db.query(models.Order).filter(models.Order.created_at >= month_start).count()
    month_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.created_at >= month_start,
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0

    total_commission = db.query(func.coalesce(func.sum(models.CommissionRecord.amount), 0)).scalar() or 0.0

    pending_orders = db.query(models.Order).filter(models.Order.status == "pending").count()
    pending_withdrawals = db.query(models.WithdrawRequest).filter(
        models.WithdrawRequest.status == "pending"
    ).count()
    pending_apps = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.status == "pending"
    ).count()

    role_stats = {}
    for r in ["user", "promoter", "creator"]:
        role_stats[r] = db.query(models.User).filter(models.User.role == r).count()

    status_stats = {}
    for s in ["pending", "paid", "processing", "completed"]:
        status_stats[s] = db.query(models.Order).filter(models.Order.status == s).count()

    trend = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = db.query(models.Order).filter(
            models.Order.created_at >= day, models.Order.created_at < next_day
        ).count()
        revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
            models.Order.created_at >= day, models.Order.created_at < next_day,
            models.Order.status.in_(["paid", "processing", "completed"])
        ).scalar() or 0.0
        trend.append({
            "date": day.strftime("%m-%d"),
            "orders": count,
            "revenue": round(revenue, 2),
        })

    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "today_orders": today_orders,
        "today_revenue": round(today_revenue, 2),
        "month_orders": month_orders,
        "month_revenue": round(month_revenue, 2),
        "total_commission_paid": round(total_commission, 2),
        "pending_orders": pending_orders,
        "pending_withdrawals": pending_withdrawals,
        "pending_applications": pending_apps,
        "role_stats": role_stats,
        "order_status_stats": status_stats,
        "daily_trend": trend,
    }


@router.get("/stats")
async def admin_stats(
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin),
):
    """管理后台数据概览（兼容旧版）"""
    pending_count = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.status == "pending"
    ).count()
    approved_count = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.status == "approved"
    ).count()
    rejected_count = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.status == "rejected"
    ).count()
    creator_count = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.status == "approved"
    ).count()
    promoter_count = db.query(models.User).filter(models.User.team_size > 0).count()
    total_users = db.query(models.User).count()
    total_revenue = db.query(func.coalesce(func.sum(models.Order.amount), 0)).filter(
        models.Order.status.in_(["paid", "processing", "completed"])
    ).scalar() or 0.0
    total_commission = db.query(func.coalesce(func.sum(models.CommissionRecord.amount), 0)).scalar() or 0.0
    pending_withdrawals = db.query(models.WithdrawRequest).filter(
        models.WithdrawRequest.status == "pending"
    ).count()

    return {
        "total_users": total_users, "creator_count": creator_count,
        "promoter_count": promoter_count,
        "pending_approvals": pending_count,
        "approved_approvals": approved_count,
        "rejected_approvals": rejected_count,
        "total_revenue": round(total_revenue, 2),
        "total_commission": round(total_commission, 2),
        "pending_withdrawals": pending_withdrawals,
    }
