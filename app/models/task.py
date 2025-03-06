import os
import json
import sqlite3
from enum import Enum

# 定义任务状态枚举
class TaskStatus(Enum):
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

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

def save_task_status(task_id, status, result_url=None, error=None):
    """保存任务状态到数据库"""
    # 确保数据库已初始化
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查任务是否已存在
    cursor.execute('SELECT id FROM tasks WHERE id = ?', (task_id,))
    exists = cursor.fetchone()
    
    if exists:
        # 更新现有任务
        cursor.execute(
            'UPDATE tasks SET status = ?, result_url = ?, error = ? WHERE id = ?',
            (status, result_url, error, task_id)
        )
    else:
        # 插入新任务
        cursor.execute(
            'INSERT INTO tasks (id, status, result_url, error) VALUES (?, ?, ?, ?)',
            (task_id, status, result_url, error)
        )
    
    conn.commit()
    conn.close()

def get_task_status(task_id):
    """获取任务状态"""
    # 确保数据库已初始化
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    
    conn.close()
    
    if task:
        return {
            'id': task['id'],
            'status': task['status'],
            'result_url': task['result_url'],
            'error': task['error'],
            'created_at': task['created_at']
        }
    
    return None 