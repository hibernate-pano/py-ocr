import os
import json
import sqlite3
from enum import Enum
from typing import Optional, Dict, Any

# 定义任务状态枚举
class TaskStatus(Enum):
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

# SQLite数据库文件路径
DB_PATH = os.path.join(os.getcwd(), 'instance', 'ocr_service.db')

def init_db():
    """初始化数据库"""
    # 确保instance目录存在
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        result_url TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def save_task_status(task_id: str, status: str, result_url: Optional[str] = None, error: Optional[str] = None):
    """
    保存任务状态
    
    参数:
        task_id: 任务ID
        status: 任务状态
        result_url: 结果URL（可选）
        error: 错误信息（可选）
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO tasks (id, status, result_url, error)
    VALUES (?, ?, ?, ?)
    ''', (task_id, status, result_url, error))
    
    conn.commit()
    conn.close()

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    获取任务状态
    
    参数:
        task_id: 任务ID
        
    返回:
        任务状态信息字典，如果任务不存在则返回None
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT status, result_url, error FROM tasks WHERE id = ?', (task_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        return {
            'status': result[0],
            'result_url': result[1],
            'error': result[2]
        }
    return None 