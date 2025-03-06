import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.models.task import TaskStatus, get_task_status, save_task_status
from app.tasks.ocr_task import process_ocr

api_bp = Blueprint('api', __name__)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传请求"""
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    
    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    # 检查文件类型是否允许
    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件类型'}), 400
    
    # 生成唯一的任务ID
    task_id = str(uuid.uuid4())
    
    # 安全地保存文件到临时目录
    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
    file.save(file_path)
    
    # 保存任务状态
    save_task_status(task_id, TaskStatus.PROCESSING.value, None, None)
    
    # 将任务加入队列
    process_ocr.delay(task_id, file_path)
    
    return jsonify({'task_id': task_id}), 200

@api_bp.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """获取任务状态"""
    task_info = get_task_status(task_id)
    
    if not task_info:
        return jsonify({'error': 'Task ID not found'}), 404
    
    response = {'status': task_info['status']}
    
    if task_info['status'] == TaskStatus.COMPLETED.value:
        response['minio_url'] = task_info['result_url']
    elif task_info['status'] == TaskStatus.FAILED.value:
        response['error'] = task_info['error']
    
    return jsonify(response), 200 