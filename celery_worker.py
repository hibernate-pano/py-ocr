"""
Celery worker 入口文件
"""
from app import create_app
from app.celery_app import init_celery

# 创建Flask应用实例
flask_app = create_app()

# 使用Flask应用实例初始化Celery
celery = init_celery(flask_app) 