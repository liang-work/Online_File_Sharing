from flask import Flask, render_template
from flask_migrate import Migrate
from flask_login import LoginManager
import os

# 导入模块
from models import db, User, Config
from routes.auth import auth_bp
from routes.main import main_bp
from routes.files import files_bp
from routes.admin import admin_bp
from routes.api import api_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fileshare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024  # 16GB

# 初始化扩展
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 注册蓝图
app.register_blueprint(auth_bp, url_prefix='')
app.register_blueprint(main_bp, url_prefix='')
app.register_blueprint(files_bp, url_prefix='')
app.register_blueprint(admin_bp, url_prefix='')
app.register_blueprint(api_bp, url_prefix='/api')

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# 错误处理器
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

@app.errorhandler(401)
def unauthorized(e):
    return render_template('errors/403.html'), 401

def init_database():
    """初始化数据库和创建默认数据"""
    with app.app_context():
        # 自动应用数据库迁移
        from flask_migrate import upgrade
        try:
            upgrade()
            print("数据库迁移应用成功")
        except Exception as e:
            print(f"数据库迁移失败: {e}")
            # 如果迁移失败，尝试创建所有表
            db.create_all()
            print("已创建数据库表")

        # 创建默认管理员用户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User()
            admin.username = 'admin'
            admin.role = 'admin'
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("默认管理员用户已创建")

        # 创建默认配置
        default_configs = [
            ('allow_registration', 'true', '是否允许用户注册'),
            ('default_max_file_size', '1024', '默认单文件大小限制(MB)'),
            ('default_max_total_files', '100', '默认总文件数量限制'),
            ('default_max_total_size', '10', '默认总文件大小限制(GB)'),
            ('background_image', '', '系统背景图片URL')
        ]

        for key, value, desc in default_configs:
            config = Config.query.filter_by(key=key).first()
            if not config:
                config = Config(key=key, value=value, description=desc)
                db.session.add(config)

        db.session.commit()
        print("默认配置已创建")

if __name__ == '__main__':
    init_database()
    app.run(debug=True,host='0.0.0.0')
