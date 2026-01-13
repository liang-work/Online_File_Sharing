#!/usr/bin/env python3
"""
文件分享系统开发管理脚本
用于管理用户、文件和系统配置
"""

import os
import sys
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade, migrate, revision, current
from werkzeug.security import generate_password_hash

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, File, Config

# 初始化迁移
migrate_obj = Migrate(app, db)

def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        print("数据库初始化完成")

def create_admin():
    """创建管理员用户"""
    username = input("输入管理员用户名: ").strip()
    password = input("输入管理员密码: ").strip()

    if not username or not password:
        print("用户名和密码不能为空")
        return

    with app.app_context():
        admin = User.query.filter_by(username=username).first()
        if admin:
            print(f"用户 '{username}' 已存在")
            return

        admin = User()
        admin.username = username
        admin.role = 'admin'
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"管理员用户 '{username}' 创建成功")

def create_user():
    """创建普通用户"""
    username = input("输入用户名: ").strip()
    password = input("输入密码: ").strip()

    if not username or not password:
        print("用户名和密码不能为空")
        return

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"用户 '{username}' 已存在")
            return

        user = User()
        user.username = username
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"用户 '{username}' 创建成功")

def list_users():
    """列出所有用户"""
    with app.app_context():
        users = User.query.all()
        if not users:
            print("暂无用户")
            return

        print(f"{'ID':<5} {'用户名':<20} {'角色':<10} {'注册时间':<20} {'文件数':<8} {'存储量(GB)':<12}")
        print("-" * 80)
        for user in users:
            file_count = user.get_total_files_count()
            total_size = user.get_total_files_size() / (1024*1024*1024)
            print(f"{user.id:<5} {user.username:<20} {user.role:<10} "
                  f"{user.created_at.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"{file_count:<8} {total_size:<12.2f}")

def delete_user():
    """删除用户及其所有文件"""
    username = input("输入要删除的用户名: ").strip()

    if not username:
        print("用户名不能为空")
        return

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"用户 '{username}' 不存在")
            return

        if user.role == 'admin':
            confirm = input(f"警告: '{username}' 是管理员用户，确定要删除吗? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("操作已取消")
                return

        # 删除用户的文件
        files = File.query.filter_by(user_id=user.id).all()
        for file in files:
            try:
                os.remove(file.filepath)
                print(f"删除文件: {file.original_filename}")
            except:
                print(f"无法删除文件: {file.original_filename}")

        # 删除数据库记录
        File.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        print(f"用户 '{username}' 及其所有文件已删除")

def reset_password():
    """重置用户密码"""
    username = input("输入用户名: ").strip()
    new_password = input("输入新密码: ").strip()

    if not username or not new_password:
        print("用户名和新密码不能为空")
        return

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"用户 '{username}' 不存在")
            return

        user.set_password(new_password)
        db.session.commit()
        print(f"用户 '{username}' 的密码已重置")

def list_files():
    """列出所有文件"""
    with app.app_context():
        files = File.query.all()
        if not files:
            print("暂无文件")
            return

        print(f"{'ID':<5} {'文件名':<30} {'用户':<15} {'大小(MB)':<10} {'公开':<6} {'上传时间':<20}")
        print("-" * 90)
        for file in files:
            try:
                size_mb = os.path.getsize(file.filepath) / (1024*1024)
            except:
                size_mb = 0
            public = "是" if file.is_public else "否"
            print(f"{file.id:<5} {file.original_filename[:28]:<30} {file.user.username:<15} "
                  f"{size_mb:<10.2f} {public:<6} "
                  f"{file.upload_time.strftime('%Y-%m-%d %H:%M'):<20}")

def delete_file():
    """删除指定文件"""
    file_id = input("输入文件ID: ").strip()

    if not file_id:
        print("文件ID不能为空")
        return

    try:
        file_id = int(file_id)
    except:
        print("文件ID必须是数字")
        return

    with app.app_context():
        file = File.query.get(file_id)
        if not file:
            print(f"文件ID '{file_id}' 不存在")
            return

        try:
            os.remove(file.filepath)
            print(f"删除文件: {file.original_filename}")
        except:
            print(f"无法删除文件: {file.original_filename}")

        db.session.delete(file)
        db.session.commit()
        print("文件记录已删除")

def show_config():
    """显示系统配置"""
    with app.app_context():
        configs = Config.query.all()
        if not configs:
            print("暂无配置")
            return

        print(f"{'键':<25} {'值':<15} {'描述'}")
        print("-" * 60)
        for config in configs:
            print(f"{config.key:<25} {config.value:<15} {config.description or ''}")

def set_config():
    """设置系统配置"""
    key = input("输入配置键: ").strip()
    value = input("输入配置值: ").strip()
    description = input("输入描述 (可选): ").strip()

    if not key or not value:
        print("配置键和值不能为空")
        return

    with app.app_context():
        config = Config.query.filter_by(key=key).first()
        if not config:
            config = Config(key=key, value=value, description=description or None)
            db.session.add(config)
        else:
            config.value = value
            if description:
                config.description = description

        db.session.commit()
        print(f"配置 '{key}' 已设置")

def clean_expired_files():
    """清理过期文件"""
    with app.app_context():
        now = datetime.utcnow()
        expired_files = File.query.filter(File.expiry_time.isnot(None), File.expiry_time < now).all()

        if not expired_files:
            print("没有过期文件")
            return

        print(f"发现 {len(expired_files)} 个过期文件")
        for file in expired_files:
            try:
                os.remove(file.filepath)
                print(f"删除过期文件: {file.original_filename}")
            except:
                print(f"无法删除过期文件: {file.original_filename}")

            db.session.delete(file)

        db.session.commit()
        print("过期文件清理完成")

def show_stats():
    """显示系统统计信息"""
    with app.app_context():
        user_count = User.query.count()
        file_count = File.query.count()
        admin_count = User.query.filter_by(role='admin').count()

        total_size = 0
        for user in User.query.all():
            total_size += user.get_total_files_size()

        public_files = File.query.filter_by(is_public=True).count()
        private_files = file_count - public_files

        print("=== 系统统计 ===")
        print(f"总用户数: {user_count}")
        print(f"管理员数: {admin_count}")
        print(f"普通用户数: {user_count - admin_count}")
        print(f"总文件数: {file_count}")
        print(f"公开文件数: {public_files}")
        print(f"私密文件数: {private_files}")
        print(f"总存储量: {total_size / (1024*1024*1024):.2f} GB")

def db_migrate():
    """生成数据库迁移"""
    with app.app_context():
        try:
            migrate(message="Auto migration")
            print("数据库迁移文件已生成")
        except Exception as e:
            print(f"生成迁移失败: {e}")

def db_upgrade():
    """应用数据库迁移"""
    with app.app_context():
        try:
            upgrade()
            print("数据库迁移已应用")
        except Exception as e:
            print(f"应用迁移失败: {e}")

def db_current():
    """显示当前数据库版本"""
    with app.app_context():
        try:
            current()
            print("当前数据库版本已显示")
        except Exception as e:
            print(f"获取版本失败: {e}")

def db_revision():
    """创建新的数据库迁移版本"""
    message = input("输入迁移描述: ").strip()
    if not message:
        message = "New migration"

    with app.app_context():
        try:
            revision(message=message)
            print("新的迁移版本已创建")
        except Exception as e:
            print(f"创建迁移版本失败: {e}")

def backup_database():
    """备份数据库"""
    import shutil
    from datetime import datetime

    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if not os.path.exists(db_path):
        print("数据库文件不存在")
        return

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"

    try:
        shutil.copy2(db_path, backup_path)
        print(f"数据库已备份到: {backup_path}")
    except Exception as e:
        print(f"备份失败: {e}")

def restore_database():
    """恢复数据库"""
    import shutil

    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')

    # 列出所有备份文件
    backup_files = [f for f in os.listdir('.') if f.startswith(os.path.basename(db_path) + '.backup_')]
    if not backup_files:
        print("没有找到备份文件")
        return

    print("可用的备份文件:")
    for i, backup in enumerate(backup_files, 1):
        print(f"{i}. {backup}")

    try:
        choice = int(input("选择要恢复的备份文件编号: ")) - 1
        if 0 <= choice < len(backup_files):
            backup_path = backup_files[choice]
            confirm = input(f"确定要恢复到 {backup_path} 吗？这将覆盖当前数据库 (yes/no): ").strip().lower()
            if confirm == 'yes':
                shutil.copy2(backup_path, db_path)
                print("数据库已恢复")
            else:
                print("操作已取消")
        else:
            print("无效选择")
    except (ValueError, IndexError):
        print("输入无效")

def main():
    """主菜单"""
    menu = """
文件分享系统管理工具
====================

用户管理:
1. 创建管理员用户
2. 创建普通用户
3. 列出所有用户
4. 删除用户
5. 重置用户密码

文件管理:
6. 列出所有文件
7. 删除文件
8. 清理过期文件

系统配置:
9. 显示配置
10. 设置配置

数据库管理:
12. 生成数据库迁移
13. 应用数据库迁移
14. 显示数据库版本
15. 创建迁移版本
16. 备份数据库
17. 恢复数据库

统计信息:
18. 显示系统统计

其他:
0. 初始化数据库
q. 退出

请选择操作: """

    while True:
        choice = input(menu).strip()

        if choice == '0':
            init_db()
        elif choice == '1':
            create_admin()
        elif choice == '2':
            create_user()
        elif choice == '3':
            list_users()
        elif choice == '4':
            delete_user()
        elif choice == '5':
            reset_password()
        elif choice == '6':
            list_files()
        elif choice == '7':
            delete_file()
        elif choice == '8':
            clean_expired_files()
        elif choice == '9':
            show_config()
        elif choice == '10':
            set_config()
        elif choice == '11':
            show_stats()
        elif choice == '12':
            db_migrate()
        elif choice == '13':
            db_upgrade()
        elif choice == '14':
            db_current()
        elif choice == '15':
            db_revision()
        elif choice == '16':
            backup_database()
        elif choice == '17':
            restore_database()
        elif choice == '18':
            show_stats()
        elif choice.lower() == 'q':
            print("再见!")
            break
        else:
            print("无效选择，请重试")

        input("\n按Enter键继续...")

if __name__ == '__main__':
    main()
