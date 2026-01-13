#!/usr/bin/env python3
"""
生成数据库迁移文件
"""

from flask_migrate import Migrate, migrate
from app import app, db

# 初始化迁移
migrate_obj = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        try:
            migrate(message="Add file metadata fields")
            print("数据库迁移文件已生成")
        except Exception as e:
            print(f"生成迁移失败: {e}")
