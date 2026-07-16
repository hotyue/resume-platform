"""
模板自动导入脚本
扫描 assets 目录，将模板文件自动导入到 templates 表
在 Docker 容器启动时执行，确保模板大厅有数据
"""
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models as m

ASSETS_DIR = os.environ.get("ASSETS_DIR", "/root/assets")

def import_templates():
    """扫描 assets 目录，导入模板到数据库"""
    db = SessionLocal()
    try:
        # 创建表
        m.Base.metadata.create_all(bind=db.get_bind())
        
        # 获取所有分类目录
        categories = []
        for entry in sorted(os.listdir(ASSETS_DIR)):
            category_dir = os.path.join(ASSETS_DIR, entry)
            if os.path.isdir(category_dir):
                categories.append((entry, category_dir))
        
        if not categories:
            print(f"⚠️  没有发现模板分类目录: {ASSETS_DIR}")
            return
        
        print(f"📁 发现 {len(categories)} 个模板分类")
        
        # 统计
        total_imported = 0
        total_skipped = 0
        total_duplicates = 0
        
        for category_name, category_dir in categories:
            # 扫描模板子目录
            template_count = 0
            for template_folder in sorted(os.listdir(category_dir)):
                folder_path = os.path.join(category_dir, template_folder)
                if not os.path.isdir(folder_path):
                    continue
                
                # 查找 jpg 和 docx 文件
                jpg_file = None
                docx_file = None
                
                for file in os.listdir(folder_path):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        jpg_file = file
                    elif file.lower().endswith(('.docx', '.doc')):
                        docx_file = file
                
                if not jpg_file or not docx_file:
                    continue
                
                # 生成路径
                jpg_path = f"/static/{category_name}/{template_folder}/{jpg_file}"
                doc_path = f"/static/{category_name}/{template_folder}/{docx_file}"
                
                # 检查是否已存在
                existing = db.query(m.Template).filter(
                    m.Template.doc_path == doc_path
                ).first()
                
                if existing:
                    total_duplicates += 1
                    continue
                
                # 创建模板记录
                template = m.Template(
                    category=category_name,
                    name=docx_file.replace('.docx', ''),
                    jpg_path=jpg_path,
                    doc_path=doc_path,
                    price=1.99,
                    is_active=True
                )
                db.add(template)
                template_count += 1
            
            if template_count > 0:
                print(f"  ✅ {category_name}: {template_count} 个模板")
            total_imported += template_count
        
        db.commit()
        
        # 最终统计
        total_count = db.query(m.Template).count()
        print(f"\n📊 导入完成:")
        print(f"   总计模板数: {total_count}")
        print(f"   本次导入: {total_imported}")
        print(f"   重复跳过: {total_duplicates}")
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_templates()
