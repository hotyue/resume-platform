"""模板路由 — list / detail"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models as m

router = APIRouter(prefix="/api/v1", tags=["templates"])


@router.get("/templates")
async def list_templates(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(m.Template).filter(m.Template.is_active == True)
    if category:
        query = query.filter(m.Template.category == category)
    if search:
        query = query.filter(m.Template.name.ilike(f"%{search}%"))
    total = query.count()
    results = query.order_by(m.Template.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "templates": [{
            "id": t.id, "name": t.name, "category": t.category,
            "price": t.price, "jpg_path": t.jpg_path,
        } for t in results],
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(m.Template).filter(m.Template.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {
        "id": t.id, "name": t.name, "category": t.category,
        "price": t.price, "jpg_path": t.jpg_path, "doc_path": t.doc_path,
    }
