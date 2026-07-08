from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from database import engine, Base, get_db, SessionLocal
import models

# 容器内素材库的挂载路径
ASSETS_DIR = "/app/assets/ResumeCollection"

app = FastAPI(title="Resume Platform API", version="0.2.1")

# 启动时自动初始化数据库并扫描素材
@app.on_event("startup")
def startup_event():
    # 自动创建所有表
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    existing_count = db.query(models.Template).count()
    if existing_count == 0 and os.path.exists(ASSETS_DIR):
        print("开始扫描模板仓库并初始化数据库...")
        templates_to_add = []
        # 遍历素材目录
        for root, dirs, files in os.walk(ASSETS_DIR):
            # 寻找任何图片和任何 word 文档
            images = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            docs = [f for f in files if f.lower().endswith(('.doc', '.docx'))]
            
            # 只要这个目录下同时有图片和文档，就认为是一个模板组合
            if images and docs:
                jpg_file = images[0]
                doc_file = docs[0]
                
                rel_root = os.path.relpath(root, ASSETS_DIR)
                # 使用一级目录名作为分类
                category = rel_root.split(os.sep)[0] if os.sep in rel_root else "其他"
                # 使用当前文件夹名作为模板名称，比如 "001"
                name = os.path.basename(root) 
                
                jpg_path = os.path.join(rel_root, jpg_file)
                doc_path = os.path.join(rel_root, doc_file)
                
                templates_to_add.append(models.Template(
                    category=category,
                    name=name,
                    jpg_path=jpg_path,
                    doc_path=doc_path
                ))
        if templates_to_add:
            db.add_all(templates_to_add)
            db.commit()
            print(f"成功入库 {len(templates_to_add)} 个简历模板！")
    db.close()

if os.path.exists(ASSETS_DIR):
    app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")

@app.get("/api/v1/health")
async def health_check(db: Session = Depends(get_db)):
    template_count = db.query(models.Template).count()
    return {"status": "ok", "db_connected": True, "templates_count": template_count}

@app.get("/api/v1/templates")
async def get_templates(skip: int = 0, limit: int = 20, category: str = None, db: Session = Depends(get_db)):
    """供前端调用的模板列表展示接口"""
    query = db.query(models.Template).filter(models.Template.is_active == True)
    if category:
        query = query.filter(models.Template.category == category)
    templates = query.offset(skip).limit(limit).all()
    return templates

@app.get("/api/v1/templates/download")
async def download_template(template_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    """受保护的下载接口"""
    if not authorization or authorization != "Bearer TEST_TOKEN":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    template = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    full_path = os.path.abspath(os.path.join(ASSETS_DIR, template.doc_path))
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File physical lost")
        
    return FileResponse(full_path, media_type='application/msword', filename=os.path.basename(full_path))
