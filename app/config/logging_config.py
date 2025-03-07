import os
import logging.config

def setup_logging():
    """配置日志记录"""
    
    # 确保日志目录存在
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志配置
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
            },
            'file': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'ocr_service.log'),
                'maxBytes': 10485760,  
                'backupCount': 5,
                'encoding': 'utf8',
            },
            'error_file': {
                'level': 'ERROR',
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'error.log'),
                'maxBytes': 10485760,  
                'backupCount': 5,
                'encoding': 'utf8',
            },
        },
        'loggers': {
            '': {  # 根记录器
                'handlers': ['console', 'file', 'error_file'],
                'level': 'INFO',
                'propagate': True
            },
            'app': {
                'handlers': ['console', 'file', 'error_file'],
                'level': 'INFO',
                'propagate': False
            },
            'werkzeug': {
                'handlers': ['console', 'file'],
                'level': 'WARNING',
                'propagate': False
            },
        }
    }
    
    # 应用配置
    logging.config.dictConfig(logging_config) 