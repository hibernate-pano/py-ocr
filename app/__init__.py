import os
from flask import Flask
from flask_cors import CORS
from celery import Celery
from dotenv import load_dotenv
from kombu import Queue, Exchange

from app.config.config import get_config

# 加载环境变量
load_dotenv()

def make_celery(app_name=__name__):
    """创建 Celery 实例并配置"""
    celery = Celery(
        app_name,
        broker=os.getenv('CELERY_BROKER_URL', 'redis://:in3BciMmiQ7Jz5aC@198.19.249.18:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://:in3BciMmiQ7Jz5aC@198.19.249.18:6379/0')
    )
    
    # 配置Celery
    celery.conf.update(
        # 基本配置
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        enable_utc=True,
        timezone='Asia/Shanghai',
        
        # 任务配置
        task_track_started=True,
        task_time_limit=int(os.getenv('CELERY_TASK_TIME_LIMIT', 1800)),
        worker_concurrency=int(os.getenv('CELERY_WORKER_CONCURRENCY', 2)),
        worker_max_tasks_per_child=int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', 100)),
        worker_prefetch_multiplier=int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', 1)),
        
        # Redis 连接配置
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=None,  # 无限重试
        broker_connection_timeout=10,
        broker_transport_options={
            'socket_timeout': 10,
            'socket_connect_timeout': 10,
            'retry_on_timeout': True,
            'max_retries': None,  # 无限重试
        },
        redis_backend_use_ssl=False,
        broker_pool_limit=10,
        redis_retry_on_timeout=True,
        redis_socket_connect_timeout=10,
        redis_socket_timeout=10,
        
        # 结果后端配置
        result_backend_transport_options={
            'retry_policy': {
                'timeout': 10.0,
                'max_retries': None,  # 无限重试
            }
        }
    )
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            from flask import current_app
            with current_app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# 创建 Celery 实例
celery = make_celery()

def create_app():
    """创建并配置Flask应用"""
    # 确保上传临时目录存在
    if not os.path.exists(get_config().UPLOAD_FOLDER):
        os.makedirs(get_config().UPLOAD_FOLDER)
    
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # 将 Celery 配置添加到 Flask 配置中
    app.config.update(
        CELERY_CONFIG=celery.conf
    )
    
    # 启用CORS
    CORS(app)
    
    # 注册蓝图
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app 