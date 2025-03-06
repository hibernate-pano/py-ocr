import os
from flask import Flask
from flask_cors import CORS
from celery import Celery

from app.config.config import get_config

# 初始化Celery
celery = Celery(__name__)

def create_app():
    """创建并配置Flask应用"""
    # 确保上传临时目录存在
    if not os.path.exists(get_config().UPLOAD_FOLDER):
        os.makedirs(get_config().UPLOAD_FOLDER)
    
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # 配置Celery
    celery.conf.update(app.config['CELERY'])
    
    # 启用CORS
    CORS(app)
    
    # 注册蓝图
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app 