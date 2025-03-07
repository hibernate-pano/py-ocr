"""
Celery 应用配置模块
"""
import os
from celery import Celery
from flask import Flask

def init_celery(app: Flask = None) -> Celery:
    """
    初始化 Celery 实例
    
    参数:
        app: Flask 应用实例（可选）
    """
    celery = Celery(
        'ocr_service',
        broker=os.getenv('CELERY_BROKER_URL', 'redis://:in3BciMmiQ7Jz5aC@198.19.249.18:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://:in3BciMmiQ7Jz5aC@198.19.249.18:6379/0'),
        include=['app.tasks.ocr_task']
    )
    
    # 配置Celery
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        enable_utc=True,
        timezone='Asia/Shanghai',
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_time_limit=1800,
        broker_connection_retry_on_startup=True,
    )

    if app:
        class ContextTask(celery.Task):
            """确保任务在应用上下文中运行"""
            abstract = True  # 这是一个抽象基类
            
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
        
        # 更新Celery配置
        celery.conf.update(app.config)
    
    return celery

# 创建 Celery 实例
celery = init_celery() 