"""订单与支付路由 — create / mock-callback / payjs / status / download / delivery-url / review / refund / my / by-id"""
import os
import uuid
import urllib.parse
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
import models as m
from auth import get_current_user
import payjs
from payjs import create_native_qrcode, verify_sign as verify_payjs_sign, PAYJS_KEY
from commission import distribute_commission, settle_custom_commission
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["orders"])
ASSETS_DIR = settings.ASSETS_DIR


def is_custom_order(order_type: str) -> bool:
    return order_type in ("custom_service", "custom")


def load_all_configs(db: Session) -> dict:
    configs = {}
    for c in db.query(m.SystemConfig).all():
        configs[c.key] = c.value
    defaults = {
        "download_price": 1.99, "custom_price": 19.99, "creator_rate": 0.30,
        "level1_rate": 0.15, "level2_rate": 0.08, "level3_rate": 0.05,
        "deposit_amount": 20.0, "auto_accept_hours": 168,
    }
    for k, v in defaults.items():
        if k not in configs:
            cfg = m.SystemConfig(key=k, value=v, description=k)
            db.add(cfg)
            db.commit()
            configs[k] = v
    return configs


# ================= Schemas =================

class CreateOrderReq:
    pass


class MockPayReq:
    pass


class PayReq:
    pass


class ReviewReq:
    pass


class RefundReq:
    pass


# ================= Endpoints =================

@router.post("/orders")
async def create_order(
    req_body: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    template = db.query(m.Template).filter(m.Template.id == req_body["template_id"]).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    configs = load_all_configs(db)
    order_type = req_body.get("order_type", "download")
    amount = configs["custom_price"] if is_custom_order(order_type) else configs["download_price"]
    order_no = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    # 自动继承用户推广关系
    ref_user_id = req_body.get("ref_user_id")
    if not ref_user_id:
        user = db.query(m.User).filter(m.User.id == current_user["id"]).first()
        if user and user.parent_id:
            ref_user_id = user.parent_id

    order = m.Order(
        order_no=order_no, user_id=current_user["id"], template_id=template.id,
        amount=amount, ref_user_id=ref_user_id, order_type=order_type,
        custom_requirements=req_body.get("custom_requirements", ""),
    )
    db.add(order)
    db.commit()
    return {"order_no": order_no, "amount": amount, "type": order_type, "template_name": template.name}


@router.post("/payments/mock-callback")
async def mock_payment_callback(req_body: dict, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == req_body["order_no"]).first()
    if not order or order.status != "pending":
        return {"status": "error"}
    if is_custom_order(order.order_type):
        order.status = "awaiting_claim"
    else:
        order.status = "completed"
        distribute_commission(order, db)
    db.commit()
    return {"status": "success"}


@router.post("/payments/payjs-qrcode")
async def payjs_qrcode(req_body: dict, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == req_body["order_no"]).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="订单状态异常")
    total_fee = int(order.amount * 100)
    result = create_native_qrcode(order.order_no, total_fee, "简历模板下载", str(order.template_id or ""))
    if not result["success"]:
        return {"success": False, "message": result["message"], "qrcode": None}
    return {"success": True, "message": "请使用微信扫码支付",
            "qrcode": result["data"]["qrcode"], "code_url": result["data"]["code_url"],
            "payjs_order_id": result["data"]["payjs_order_id"], "amount": order.amount}


@router.post("/payments/payjs-notify")
async def payjs_notify(request: Request, db: Session = Depends(get_db)):
    body = await request.form()
    params = dict(body)
    if not verify_payjs_sign(params, PAYJS_KEY):
        logger.warning(f"PayJS 回调签名验证失败: {params}")
        return "sign error"
    if params.get("return_code") != "1":
        return "fail"
    order = db.query(m.Order).filter(m.Order.order_no == params.get("out_trade_no", "")).first()
    if not order:
        return "order not found"
    if order.status in ("paid", "completed", "awaiting_claim"):
        return "success"
    if is_custom_order(order.order_type):
        order.status = "awaiting_claim"
    else:
        order.status = "completed"
        distribute_commission(order, db)
    db.commit()
    return "success"


@router.get("/orders/status/{order_no}")
async def get_order_status(order_no: str, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"order_no": order.order_no, "status": order.status, "amount": order.amount, "order_type": order.order_type}


@router.get("/orders/download/{order_no}")
async def download_by_order(order_no: str, db: Session = Depends(get_db)):
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order or order.status not in ["paid", "processing", "completed"]:
        raise HTTPException(status_code=403, detail="未支付或无权下载")
    template = db.query(m.Template).filter(m.Template.id == order.template_id).first()
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    return FileResponse(full_path, media_type="application/msword", filename=f"{template.name}.doc")


@router.get("/orders/{order_no}/delivery-url")
async def download_delivery_file(
    order_no: str,
    file_type: Optional[str] = Query(None, description="pdf 或 word"),
    type_f: Optional[str] = Query(None, alias="type", description="pdf 或 word (兼容别名)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """下载交付文件 — 后端代理，避免内网 S3 地址无法访问"""
    ft = file_type or type_f or "pdf"
    delivery = db.query(m.Delivery).filter(m.Delivery.order_no == order_no).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="该订单暂无交付文件")

    # 权限校验
    order = db.query(m.Order).filter(m.Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.user_id != current_user["id"] and order.creator_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权下载该文件")

    if ft == "pdf":
        key = delivery.pdf_key
        filename = delivery.pdf_filename
    elif ft == "word":
        key = delivery.word_key
        filename = delivery.word_filename
    else:
        raise HTTPException(status_code=400, detail="file_type 必须是 pdf 或 word")

    if not key:
        raise HTTPException(status_code=404, detail=f"未找到 {ft} 文件")

    try:
        from storage import get_storage, StorageError
        storage = get_storage()
        resp = storage.client.get_object(Bucket=storage.bucket, Key=key)
        body = resp["Body"]
    except StorageError as e:
        raise HTTPException(status_code=503, detail=f"读取文件失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"S3 读取失败: {e}")

    content_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
    }
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
    media_type = content_types.get(ext, "application/octet-stream")

    encoded_filename = urllib.parse.quote(filename.encode("utf-8"))
    disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

    return StreamingResponse(body, media_type=media_type, headers={"Content-Disposition": disposition})


@router.post("/orders/review")
async def review_delivery(
    req_body: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    order = db.query(m.Order).filter(
        m.Order.order_no == req_body["order_no"], m.Order.user_id == current_user["id"],
        m.Order.status == "delivered"
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="订单异常或无权操作")
    db.add(m.Review(order_no=req_body["order_no"], result=req_body["result"], buyer_remark=req_body.get("buyer_remark", "")))
    if req_body["result"] == "accepted":
        order.status = "accepted"
        order.accepted_at = datetime.now()
        settle_custom_commission(order, db)
    elif req_body["result"] == "rejected":
        order.status = "in_progress"
        for p in db.query(m.CommissionPending).filter(
            m.CommissionPending.order_no == req_body["order_no"],
            m.CommissionPending.status == "pending"
        ).all():
            p.status = "cancelled"
    else:
        raise HTTPException(status_code=400, detail="验收结果必须是 accepted 或 rejected")
    db.commit()
    msg = "验收通过，佣金已到账" if req_body["result"] == "accepted" else "已退回制作者重新制作"
    return {"status": "success", "message": msg}


@router.post("/orders/refund")
async def request_refund(
    req_body: dict, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    order = db.query(m.Order).filter(
        m.Order.order_no == req_body["order_no"], m.Order.user_id == current_user["id"],
        m.Order.order_type.in_(("custom_service", "custom"))
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status not in ("delivered", "in_progress"):
        raise HTTPException(status_code=400, detail="仅拒收场景可退款")
    if db.query(m.RefundRequest).filter(
        m.RefundRequest.order_no == req_body["order_no"],
        m.RefundRequest.status.in_(["approved", "pending"])
    ).first():
        raise HTTPException(status_code=400, detail="该订单已有退款申请")
    refund_amount = round(order.amount / 2, 2)
    creator_deduction = round(order.amount / 2, 2)
    r = m.RefundRequest(
        order_no=req_body["order_no"], buyer_id=current_user["id"], creator_id=order.creator_id,
        refund_amount=refund_amount, creator_deduction=creator_deduction, reason=req_body.get("reason", ""),
    )
    db.add(r)
    order.status = "refund_requested"
    db.commit()
    return {"id": r.id, "refund_amount": refund_amount, "creator_deduction": creator_deduction,
            "status": "pending", "message": "退款申请已提交，等待管理员审核"}


@router.get("/orders/my")
async def get_my_orders(
    order_type: str = "custom_service", db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):
    orders = db.query(m.Order).filter(
        m.Order.user_id == current_user["id"], m.Order.order_type == order_type
    ).order_by(m.Order.created_at.desc()).all()
    result = []
    for o in orders:
        template = db.query(m.Template).filter(m.Template.id == o.template_id).first()
        creator = db.query(m.User).filter(m.User.id == o.creator_id).first() if o.creator_id else None
        result.append({
            "id": o.id, "order_no": o.order_no,
            "template_name": template.name if template else "未知模板",
            "order_type": o.order_type, "amount": o.amount, "status": o.status,
            "custom_requirements": o.custom_requirements, "creator_id": o.creator_id,
            "creator_name": creator.username if creator else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
            "freeze_until": o.freeze_until.isoformat() if o.freeze_until else None,
            "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
        })
    return result


@router.get("/orders/by-id/{order_id}")
async def get_order_by_id(order_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """按数据库ID获取订单详情（用于聊天标题等场景）"""
    order = db.query(m.Order).filter(m.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"id": order.id, "order_no": order.order_no, "status": order.status, "order_type": order.order_type}
