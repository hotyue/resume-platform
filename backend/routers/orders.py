"""订单与支付路由：创建订单、支付回调、PayJS、订单状态、下载"""
import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import payjs
from commission import distribute_commission
from schemas import CreateOrderReq, MockPayReq, PayReq

from config import settings

router = APIRouter(prefix="/api/v1", tags=["orders"])
ASSETS_DIR = settings.ASSETS_DIR


@router.get("/orders/my/active-check")
async def check_active_orders(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """检查当前用户是否有进行中的定制订单（in_progress / delivered / awaiting_claim）"""
    count = (
        db.query(models.Order)
        .filter(
            models.Order.user_id == current_user["id"],
            models.Order.order_type == "custom_service",
            models.Order.status.in_(["in_progress", "delivered", "awaiting_claim"]),
        )
        .count()
    )
    return {"has_active": count > 0, "count": count}


@router.get("/orders/my")
async def get_my_custom_orders(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户的所有定制订单"""
    orders = (
        db.query(models.Order)
        .filter(
            models.Order.user_id == current_user["id"],
            models.Order.order_type == "custom_service",
        )
        .order_by(models.Order.created_at.desc())
        .all()
    )
    result = []
    for o in orders:
        template = db.query(models.Template).filter(models.Template.id == o.template_id).first()
        creator = db.query(models.User).filter(models.User.id == o.creator_id).first() if o.creator_id else None
        result.append({
            "id": o.id,
            "order_no": o.order_no,
            "status": o.status,
            "amount": o.amount,
            "template_name": template.name if template else "未知",
            "creator_name": creator.username if creator else None,
            "custom_requirements": o.custom_requirements,
            "created_at": str(o.created_at),
        })
    return result


@router.post("/orders")
async def create_order(req: CreateOrderReq, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == req.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    amount = 19.99 if req.order_type == "custom_service" else template.price
    order_no = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    db.add(models.Order(
        order_no=order_no, template_id=template.id, amount=amount,
        ref_user_id=req.ref_user_id, order_type=req.order_type,
        custom_requirements=req.custom_requirements
    ))
    db.commit()
    return {"order_no": order_no, "amount": amount, "type": req.order_type}


@router.post("/payments/mock-callback")
async def mock_payment_callback(req: MockPayReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no).first()
    if not order or order.status != "pending":
        return {"status": "error"}
    order.status = "paid"
    distribute_commission(order, db)
    db.commit()
    return {"status": "success"}


@router.post("/payments/payjs-qrcode")
async def payjs_qrcode(req: PayReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="订单状态异常")
    total_fee = int(order.amount * 100)
    result = payjs.create_native_qrcode(
        out_trade_no=order.order_no, total_fee=total_fee,
        body="简历模板下载", attach=str(order.template_id or ""),
    )
    if not result["success"]:
        return {"success": False, "message": result["message"], "qrcode": None}
    return {
        "success": True, "message": "请使用微信扫码支付",
        "qrcode": result["data"]["qrcode"], "code_url": result["data"]["code_url"],
        "payjs_order_id": result["data"]["payjs_order_id"], "amount": order.amount,
    }


@router.post("/payments/payjs-notify")
async def payjs_notify(request: Request, db: Session = Depends(get_db)):
    body = await request.form()
    params = dict(body)
    if not payjs.verify_sign(params, payjs.PAYJS_KEY):
        logging.warning(f"PayJS 回调签名验证失败: {params}")
        return "sign error"
    if params.get("return_code") != "1":
        return "fail"
    out_trade_no = params.get("out_trade_no", "")
    order = db.query(models.Order).filter(models.Order.order_no == out_trade_no).first()
    if not order:
        return "order not found"
    if order.status == "paid":
        return "success"
    order.status = "paid"
    distribute_commission(order, db)
    db.commit()
    return "success"


@router.get("/orders/status/{order_no}")
async def get_order_status(order_no: str, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {
        "order_no": order.order_no, "status": order.status,
        "amount": order.amount, "order_type": order.order_type
    }


@router.get("/orders/download/{order_no}")
async def download_by_order(order_no: str, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order or order.status not in ["paid", "processing", "completed"]:
        raise HTTPException(status_code=403, detail="未支付或无权下载")
    template = db.query(models.Template).filter(models.Template.id == order.template_id).first()
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    return FileResponse(full_path, media_type='application/msword', filename=f"{template.name}.doc")
