import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from app.config.config import Config
from app.celery_app import init_celery

# 加载环境变量
load_dotenv()

def create_app():
    """创建并配置Flask应用"""
    # 确保上传临时目录存在
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)
    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 初始化 Celery
    celery = init_celery(app)
    app.config.update(CELERY=celery)
    
    # 启用CORS
    CORS(app)
    
    # 注册蓝图
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app 