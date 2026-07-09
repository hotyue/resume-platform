"""制作者路由：入驻申请、申请状态、订单列表、抢单、交付"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
import models
from schemas import CreatorApplyReq, TakeOrderReq

router = APIRouter(prefix="/api/v1/creator", tags=["creator"])


@router.post("/apply")
async def creator_apply(req: CreatorApplyReq, db: Session = Depends(get_db)):
    """提交制作者入驻申请"""
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    existing = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.user_id == req.user_id
    ).first()
    if existing:
        if existing.status == "pending":
            raise HTTPException(status_code=400, detail="已有待审核的申请，请等待审核结果")
        elif existing.status == "approved":
            raise HTTPException(status_code=400, detail="你已经是制作者了")
        # rejected → 覆盖旧申请
        existing.real_name = req.real_name
        existing.phone = req.phone
        existing.wechat = req.wechat
        existing.specialty = req.specialty
        existing.portfolio_desc = req.portfolio_desc
        existing.experience = req.experience
        existing.status = "pending"
        existing.review_remark = None
        existing.reviewed_at = None
        existing.created_at = datetime.now()
        db.commit()
        return {"id": existing.id, "status": "pending", "message": "申请已重新提交，等待管理员审核"}
    else:
        app_record = models.CreatorApplication(
            user_id=req.user_id, real_name=req.real_name, phone=req.phone,
            wechat=req.wechat, specialty=req.specialty, portfolio_desc=req.portfolio_desc,
            experience=req.experience, status="pending"
        )
        db.add(app_record)
        db.commit()
        return {"id": app_record.id, "status": "pending", "message": "申请已提交，等待管理员审核"}


@router.get("/application-status/{user_id}")
async def get_application_status(user_id: int, db: Session = Depends(get_db)):
    """查看自己的申请状态"""
    app_record = db.query(models.CreatorApplication).filter(
        models.CreatorApplication.user_id == user_id
    ).first()
    if not app_record:
        return {"has_applied": False}
    return {
        "has_applied": True, "id": app_record.id, "status": app_record.status,
        "real_name": app_record.real_name, "phone": app_record.phone,
        "wechat": app_record.wechat, "specialty": app_record.specialty,
        "portfolio_desc": app_record.portfolio_desc, "experience": app_record.experience,
        "review_remark": app_record.review_remark,
        "created_at": str(app_record.created_at),
        "reviewed_at": str(app_record.reviewed_at) if app_record.reviewed_at else None,
    }


@router.get("/orders")
async def get_creator_orders(tab: str = "pending", db: Session = Depends(get_db)):
    query = db.query(models.Order, models.Template).join(models.Template).filter(
        models.Order.order_type == "custom_service"
    )
    if tab == "pending":
        results = query.filter(
            models.Order.status == "paid", models.Order.creator_id == None
        ).all()
    elif tab == "mine":
        results = query.filter(models.Order.creator_id == 2).all()
    else:
        results = query.filter(models.Order.creator_id == 2).all()

    return [{
        "order_no": o.order_no, "amount": o.amount, "status": o.status,
        "requirements": o.custom_requirements, "created_at": str(o.created_at),
        "template_name": f"{t.category}-{t.name}",
    } for o, t in results]


@router.post("/take")
async def take_order(req: TakeOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.order_no == req.order_no, models.Order.status == "paid",
        models.Order.creator_id == None
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="订单已被抢走或状态错误")
    order.creator_id = 2
    order.status = "processing"
    db.commit()
    return {"status": "success"}


@router.post("/deliver")
async def deliver_order(req: TakeOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.order_no == req.order_no, models.Order.creator_id == 2,
        models.Order.status == "processing"
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="订单异常")
    order.status = "completed"
    creator = db.query(models.User).filter(models.User.id == 2).first()
    creator.wallet_balance += (order.amount * 0.30)
    db.commit()
    return {"status": "success"}
