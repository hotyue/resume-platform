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
app = FastAPI(title="Resume Platform API", version="0.4.1")

# --- 请求体模型 ---
class CreateOrderReq(BaseModel):
    template_id: int
    # 核心修复：使用 Optional 明确允许 null 值
    ref_user_id: Optional[int] = None

class MockPayReq(BaseModel):
    order_no: str

# --- 启动事件 (初始化与扫描) ---
@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    existing_count = db.query(models.Template).count()
    if existing_count == 0 and os.path.exists(ASSETS_DIR):
        print("开始扫描模板仓库...")
        templates_to_add = []
        for root, dirs, files in os.walk(ASSETS_DIR):
            images = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            docs = [f for f in files if f.lower().endswith(('.doc', '.docx'))]
            if images and docs:
                rel_root = os.path.relpath(root, ASSETS_DIR)
                category = rel_root.split(os.sep)[0] if os.sep in rel_root else "其他"
                templates_to_add.append(models.Template(
                    category=category, name=os.path.basename(root),
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

# ================= 核心交易链路 =================

@app.post("/api/v1/orders")
async def create_order(req: CreateOrderReq, db: Session = Depends(get_db)):
    """1. 创建订单"""
    template = db.query(models.Template).filter(models.Template.id == req.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    order_no = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    new_order = models.Order(
        order_no=order_no,
        template_id=template.id,
        amount=template.price,
        status="pending",
        ref_user_id=req.ref_user_id,
        order_type="download"
    )
    db.add(new_order)
    db.commit()
    return {"order_no": order_no, "amount": template.price}

@app.post("/api/v1/payments/mock-callback")
async def mock_payment_callback(req: MockPayReq, db: Session = Depends(get_db)):
    """2. 模拟支付网关异步回调"""
    order = db.query(models.Order).filter(models.Order.order_no == req.order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "paid":
        return {"status": "already_paid"}
    
    order.status = "paid"
    
    if order.ref_user_id:
        promoter = db.query(models.User).filter(models.User.id == order.ref_user_id).first()
        if promoter:
            promoter.wallet_balance += (order.amount * 0.20)
            
    db.commit()
    return {"status": "success", "msg": "模拟支付成功，发货权限已释放"}

@app.get("/api/v1/orders/download/{order_no}")
async def download_by_order(order_no: str, db: Session = Depends(get_db)):
    """3. 凭已支付订单号提取文件"""
    order = db.query(models.Order).filter(models.Order.order_no == order_no).first()
    if not order or order.status != "paid":
        raise HTTPException(status_code=403, detail="未找到该订单或订单未支付")
        
    template = db.query(models.Template).filter(models.Template.id == order.template_id).first()
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件物理丢失")
        
    return FileResponse(full_path, media_type='application/msword', filename=f"{template.name}_{os.path.basename(full_path)}")
