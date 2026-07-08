from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import os
import uuid

from database import engine, Base, get_db, SessionLocal
import models

ASSETS_DIR = "/app/assets/ResumeCollection"
app = FastAPI(title="Resume Platform API", version="0.6.1")

class CreateOrderReq(BaseModel):
    template_id: int
    ref_user_id: Optional[int] = None
    order_type: str = "download"
    custom_requirements: Optional[str] = None

class MockPayReq(BaseModel):
    order_no: str
    
class TakeOrderReq(BaseModel):
    order_no: str

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    if db.query(models.User).count() == 0:
        db.add(models.User(id=1, username="大学辅导员_张老师", role="promoter", wallet_balance=158.50))
        db.add(models.User(id=2, username="简历达人_李四", role="creator", wallet_balance=0.0))
        db.commit()

    if db.query(models.Template).count() == 0 and os.path.exists(ASSETS_DIR):
        print("开始扫描模板仓库...")
        templates_to_add = []
        for root, dirs, files in os.walk(ASSETS_DIR):
            images = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            docs = [f for f in files if f.lower().endswith(('.doc', '.docx'))]
            if images and docs:
                rel_root = os.path.relpath(root, ASSETS_DIR)
                cat = rel_root.split(os.sep)[0] if os.sep in rel_root else "其他"
                templates_to_add.append(models.Template(
                    category=cat, name=os.path.basename(root),
                    jpg_path=os.path.join(rel_root, images[0]),
                    doc_path=os.path.join(rel_root, docs[0])
                ))
        if templates_to_add:
            db.add_all(templates_to_add)
            db.commit()
    db.close()

if os.path.exists(ASSETS_DIR):
    app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")

@app.get("/api/v1/health")
async def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "templates_count": db.query(models.Template).count()}

@app.get("/api/v1/templates")
async def get_templates(skip: int = 0, limit: int = 50, category: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Template).filter(models.Template.is_active == True)
    if category: query = query.filter(models.Template.category == category)
    return query.offset(skip).limit(limit).all()

# ================= 订单与交易 =================

@app.post("/api/v1/orders")
async def create_order(req: CreateOrderReq, db: Session = Depends(get_db)):
    template = db.query(models.Template).filter(models.Template.id == req.template_id).first()
    if not template: raise HTTPException(status_code=404, detail="模板不存在")
    
    amount = 9.99 if req.order_type == "custom_service" else template.price
    order_no = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    
    db.add(models.Order(
        order_no=order_no, template_id=template.id, amount=amount, 
        ref_user_id=req.ref_user_id, order_type=req.order_type,
        custom_requirements=req.custom_requirements
    ))
    db.commit()
    return {"order_no": order_no, "amount": amount, "type": req.order_type}

@app.post("/api/v1/payments/mock-callback")
async def mock_payment_callback(req: MockPayReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no).first()
    if not order or order.status != "pending": return {"status": "error"}
    
    order.status = "paid"
    if order.ref_user_id:
        promoter = db.query(models.User).filter(models.User.id == order.ref_user_id).first()
        if promoter: promoter.wallet_balance += (order.amount * 0.20)
    db.commit()
    return {"status": "success"}

@app.get("/api/v1/orders/download/{order_no}")
async def download_by_order(order_no: str, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    # 核心修复：允许在已付款、制作中、已完成状态下都可以提取底稿文件
    if not order or order.status not in ["paid", "processing", "completed"]: 
        raise HTTPException(status_code=403, detail="未支付或无权下载")
        
    template = db.query(models.Template).filter(models.Template.id == order.template_id).first()
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    return FileResponse(full_path, media_type='application/msword', filename=f"{template.name}.doc")

# ================= 众包大厅接口 =================

@app.get("/api/v1/creator/orders")
async def get_creator_orders(tab: str = "pending", db: Session = Depends(get_db)):
    query = db.query(models.Order, models.Template).join(models.Template).filter(models.Order.order_type == "custom_service")
    if tab == "pending":
        results = query.filter(models.Order.status == "paid", models.Order.creator_id == None).all()
    else:
        results = query.filter(models.Order.creator_id == 2).all()
        
    res_list = []
    for o, t in results:
        res_list.append({
            "order_no": o.order_no, "amount": o.amount, "status": o.status,
            "requirements": o.custom_requirements, "created_at": o.created_at,
            "template_name": f"{t.category}-{t.name}"
        })
    return res_list

@app.post("/api/v1/creator/take")
async def take_order(req: TakeOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no, models.Order.status == "paid", models.Order.creator_id == None).first()
    if not order: raise HTTPException(status_code=400, detail="订单已被抢走或状态错误")
    order.creator_id = 2
    order.status = "processing"
    db.commit()
    return {"status": "success"}

@app.post("/api/v1/creator/deliver")
async def deliver_order(req: TakeOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no, models.Order.creator_id == 2, models.Order.status == "processing").first()
    if not order: raise HTTPException(status_code=400, detail="订单异常")
    order.status = "completed"
    creator = db.query(models.User).filter(models.User.id == 2).first()
    creator.wallet_balance += (order.amount * 0.30)
    db.commit()
    return {"status": "success"}

@app.get("/api/v1/user/profile")
async def get_user_profile(db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == 2).first()
    return {"id": user.id, "username": user.username, "role": user.role, "wallet_balance": round(user.wallet_balance, 2)}
