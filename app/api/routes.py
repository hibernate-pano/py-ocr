import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.models.task import TaskStatus, get_task_status, save_task_status
from app.tasks.ocr_task import process_ocr
from app.services.ocr_service import ocr_service
from app.celery_app import celery  # 从正确的模块导入 celery

api_bp = Blueprint('api', __name__)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传请求"""
    try:
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
        
        # 确保上传目录存在
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # 安全地保存文件到临时目录
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, f"{task_id}_{filename}")
        
        # 将文件内容读入内存
        file_content = file.read()
        
        # 确保文件内容不为空
        if not file_content:
            return jsonify({'error': '文件内容为空'}), 400
        
        # 使用二进制模式写入文件
        with open(file_path, 'wb') as f:
            f.write(file_content)
            f.flush()
            os.fsync(f.fileno())  # 确保文件完全写入磁盘
        
        # 验证文件是否成功保存和可读
        try:
            with open(file_path, 'rb') as f:
                f.read(1)  # 尝试读取一个字节来验证文件可读
        except Exception as e:
            return jsonify({'error': f'文件保存后无法读取: {str(e)}'}), 500
            
        # 保存任务状态
        save_task_status(task_id, TaskStatus.PROCESSING.value, None, None)
        
        # 将任务加入队列
        process_ocr.delay(task_id, file_path)
        
        return jsonify({
            'task_id': task_id,
            'message': '文件上传成功，开始处理'
        }), 200
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({
            'error': f'文件上传失败: {str(e)}'
        }), 500

@api_bp.route('/status/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务状态"""
    task_info = get_task_status(task_id)
    
    if task_info is None:
        return jsonify({'error': 'Task ID not found'}), 404
        
    return jsonify(task_info), 200

@api_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id):
    """
    取消正在进行的OCR任务
    
    参数:
        task_id: 任务ID
    """
    # 获取任务状态
    task_info = get_task_status(task_id)
    
    if task_info is None:
        return jsonify({'error': 'Task ID not found'}), 404
    
    # 检查任务是否可以取消
    if task_info['status'] != TaskStatus.PROCESSING.value:
        return jsonify({
            'error': '只能取消处理中的任务',
            'current_status': task_info['status']
        }), 400
    
    # 取消OCR服务中的任务
    cancelled = ocr_service.cancel_task(task_id)
    
    # 取消Celery任务
    celery.control.revoke(task_id, terminate=True)
    
    if cancelled:
        # 更新任务状态为已取消
        save_task_status(task_id, TaskStatus.CANCELLED.value, None, "任务已被用户取消")
        return jsonify({'message': '任务已取消'}), 200
    else:
        return jsonify({'error': '任务取消失败'}), 400 