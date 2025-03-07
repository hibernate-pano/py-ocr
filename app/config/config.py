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
        'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'enable_utc': True,
    }
    
    # MinIO配置
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    MINIO_SECURE = os.getenv('MINIO_SECURE', 'False') == 'True'
    MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'ocr-markdown')
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///ocr_service.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OCR配置
    OCR_LANGUAGES = os.getenv('OCR_LANGUAGES', 'chi_sim+eng')  # 默认中文+英文
    
    # 硅基流动API配置
    SILICON_FLOW_API_KEY = os.getenv('SILICON_FLOW_API_KEY', '')
    SILICON_FLOW_API_URL = os.getenv('SILICON_FLOW_API_URL', 'https://api.siliconflow.com/v1')
    
    # Ollama配置
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2-vision:11b')
    # 设置Ollama API超时时间（秒）
    OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', 120))
    
    # Ollama-OCR配置
    OLLAMA_OUTPUT_FORMAT = os.getenv('OLLAMA_OUTPUT_FORMAT', 'plain_text')

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