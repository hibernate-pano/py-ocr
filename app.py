import os
from app import create_app
from app.config.logging_config import setup_logging

# 设置日志
setup_logging()

# 创建应用
app = create_app()

if __name__ == '__main__':
    # 确保临时目录存在
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # 启动应用
    app.run(host='0.0.0.0', port=15000) 