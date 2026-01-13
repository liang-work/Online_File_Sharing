#!/usr/bin/env python3
"""
初始化Flask-Migrate迁移文件夹
"""

import os
from flask_migrate import Migrate
from app import app, db

# 初始化迁移
migrate = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        # 创建迁移文件夹
        os.makedirs('migrations', exist_ok=True)

        # 初始化迁移
        from flask_migrate import init
        try:
            init()
            print("Flask-Migrate已初始化")
        except Exception as e:
            print(f"初始化失败: {e}")
