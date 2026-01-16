from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import os

db = SQLAlchemy()

# 配置模型
class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255))

# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default='user')  # admin, user, guest
    nickname = db.Column(db.String(150))  # 昵称
    avatar_url = db.Column(db.String(500))  # 头像链接
    max_file_size = db.Column(db.BigInteger, default=1024*1024*1024)  # 默认1GB
    max_total_files = db.Column(db.Integer, default=100)  # 默认100个文件
    max_total_size = db.Column(db.BigInteger, default=10*1024*1024*1024)  # 默认10GB
    language = db.Column(db.String(10), default='zh')  # 语言设置
    theme = db.Column(db.String(10), default='light')  # 主题设置
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_total_files_count(self):
        return File.query.filter_by(user_id=self.id).count()

    def get_total_files_size(self):
        total_size = 0
        for file in File.query.filter_by(user_id=self.id).all():
            try:
                total_size += os.path.getsize(file.filepath)
            except:
                pass
        return total_size

# 文件模型
class File(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    raw_filename = db.Column(db.String(255), nullable=False)  # 完全原始的文件名
    filepath = db.Column(db.String(500), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    password = db.Column(db.String(150))
    expiry_time = db.Column(db.DateTime)
    # 新增权限字段
    allow_edit = db.Column(db.Boolean, default=False)  # 允许编辑
    allow_download = db.Column(db.Boolean, default=True)  # 允许下载
    allow_view = db.Column(db.Boolean, default=True)  # 允许查看
    share_type = db.Column(db.String(20), default='public')  # public, link_only, specified_users
    allowed_users = db.Column(db.Text)  # JSON格式的允许用户列表
    # 新增详细信息字段
    description = db.Column(db.Text)  # 文件描述
    discovered_by = db.Column(db.String(150))  # 发现者
    tags = db.Column(db.String(500))  # 标签，用逗号分隔

    user = db.relationship('User', backref=db.backref('files', lazy=True))

# 分块上传任务模型
class UploadTask(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_hash = db.Column(db.String(128), nullable=False)  # 文件哈希
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    chunk_size = db.Column(db.BigInteger, nullable=False)
    chunks_count = db.Column(db.Integer, nullable=False)
    pool_id = db.Column(db.String(36))  # 可选的池ID
    bundle_id = db.Column(db.String(36))  # 可选的捆绑ID
    encrypt_password = db.Column(db.String(150))  # 加密密码
    expired_at = db.Column(db.DateTime)  # 过期时间
    share_options = db.Column(db.Text)  # JSON格式的分享选项
    status = db.Column(db.String(20), default='uploading')  # uploading, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('upload_tasks', lazy=True))

# 分块模型
class UploadChunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey('upload_task.id'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_size = db.Column(db.BigInteger, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship('UploadTask', backref=db.backref('chunks', lazy=True))
