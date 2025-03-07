import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用基础配置"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key')
    
    # Flask配置
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'temp')
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'pdf,png,jpg,jpeg,tiff').split(','))
    
    # Celery配置
    CELERY = {
        'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://:in3BciMmiQ7Jz5aC@198.19.249.18:6379/0'),
        'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://:in3BciMmiQ7Jz5aC@198.19.249.18:6379/0'),
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'enable_utc': True,
    }
    
    # MinIO配置
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', '198.19.249.18:9000')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'oZMHvmBAwOpiyMBXvD5Q')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', '1W2Y3TFNrc8yPknXoSbYsOHC4a9BoDYsKA0f5LIT')
    MINIO_SECURE = os.getenv('MINIO_SECURE', 'False') == 'True'
    MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'pdf-ocr-markdown-bucket')
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///ocr_service.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False

# 根据环境变量选择配置
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    config_name = os.getenv('FLASK_ENV', 'development')
    return config.get(config_name, config['default']) 