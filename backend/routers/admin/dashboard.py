"""管理员路由 — dashboard / stats"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
import models as m
from auth import require_admin

router = APIRouter()


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
