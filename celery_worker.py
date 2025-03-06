import os
from app import create_app, celery
from app.config.logging_config import setup_logging

# 设置日志
setup_logging()

# 确保临时目录存在
app = create_app()
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 推送应用上下文
app.app_context().push()

# 自动导入所有任务
import app.tasks.ocr_task 