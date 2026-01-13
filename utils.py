import hashlib
import os
from models import Config

def calculate_file_hash(file_path, hash_type='sha256'):
    """计算文件哈希值"""
    hash_func = hashlib.sha256() if hash_type == 'sha256' else hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def get_config_value(key, default=None):
    """获取配置值"""
    config = Config.query.filter_by(key=key).first()
    return config.value if config else default

def get_config_dict():
    """获取所有配置的字典"""
    configs = Config.query.all()
    return {config.key: config.value for config in configs}

def is_registration_allowed():
    """检查是否允许用户注册"""
    return get_config_value('allow_registration', 'true').lower() == 'true'
