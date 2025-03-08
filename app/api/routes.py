import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from app.models.task import TaskStatus, get_task_status, save_task_status
from app.tasks.ocr_task import process_ocr
from app.tasks.llm_task import process_llm
from app.tasks.ollama_ocr_task import process_ollama_ocr
from app.services.ocr_service import ocr_service
from app.services.llm_service import llm_service
from app.services.ollama_ocr_service import ollama_ocr_service
from app.celery_app import celery

api_bp = Blueprint('api', __name__)

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# 统一的文件上传接口，支持不同类型的OCR处理
@api_bp.route('/file/upload', methods=['POST'])
def unified_upload_file():
    """
    处理文件上传请求并启动OCR处理
    
    查询参数:
        ocr_type: OCR处理类型，可选值为 standard (默认), llm, ollama
    """
    try:
        # 确定处理类型
        ocr_type = request.args.get('ocr_type', 'standard').lower()
        
        # 添加日志以便调试
        current_app.logger.info(f"统一上传接口收到请求，OCR类型: {ocr_type}, 参数: {request.args}")
        
        if ocr_type not in ['standard', 'llm', 'ollama']:
            return jsonify({'error': f'不支持的OCR类型: {ocr_type}', 'code': 'INVALID_OCR_TYPE'}), 400
        
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件', 'code': 'NO_FILE_UPLOADED'}), 400
        
        file = request.files['file']
        
        # 检查文件名是否为空
        if file.filename == '':
            return jsonify({'error': '未选择文件', 'code': 'NO_FILE_SELECTED'}), 400
        
        # 检查文件类型是否允许
        if not allowed_file(file.filename):
            return jsonify({
                'error': '不支持的文件类型',
                'code': 'UNSUPPORTED_FILE_TYPE',
                'supported_types': list(current_app.config['ALLOWED_EXTENSIONS'])
            }), 400
        
        # 检查文件大小是否超过限制 (针对Ollama类型增加检查)
        if ocr_type == 'ollama':
            content = file.read()
            file.seek(0)  # 重置文件指针
            if len(content) > current_app.config['MAX_CONTENT_LENGTH']:
                return jsonify({
                    'error': '文件大小超过限制',
                    'code': 'FILE_TOO_LARGE',
                    'max_size': current_app.config['MAX_CONTENT_LENGTH']
                }), 400
        
        # 生成唯一的任务ID
        task_id = str(uuid.uuid4())
        
        # 确保上传目录存在
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # 安全地保存文件到临时目录
        filename = secure_filename(file.filename)
        
        # 根据不同处理类型添加前缀
        prefix = ""
        if ocr_type == 'llm':
            prefix = "llm_"
        file_path = os.path.join(upload_folder, f"{prefix}{task_id}_{filename}")
        
        # 为Ollama类型直接保存文件
        if ocr_type == 'ollama':
            file.save(file_path)
        else:
            # 读取文件内容并写入
            file_content = file.read()
            
            # 确保文件内容不为空
            if not file_content:
                return jsonify({'error': '文件内容为空', 'code': 'EMPTY_FILE'}), 400
            
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
                return jsonify({'error': f'文件保存后无法读取: {str(e)}', 'code': 'FILE_READ_ERROR'}), 500
        
        # 保存任务状态
        save_task_status(task_id, TaskStatus.PROCESSING.value, None, None)
        
        # 根据不同处理类型将任务加入队列
        if ocr_type == 'llm':
            process_llm.delay(task_id, file_path)
            message = '文件上传成功，开始LLM处理'
        elif ocr_type == 'ollama':
            process_ollama_ocr.delay(task_id, file_path)
            message = '文件上传成功，正在使用Ollama OCR处理中'
        else:  # standard
            process_ocr.delay(task_id, file_path)
            message = '文件上传成功，开始处理'
        
        return jsonify({
            'task_id': task_id,
            'message': message,
            'ocr_type': ocr_type
        }), 200
    except Exception as e:
        error_log = f"文件上传失败 (类型: {ocr_type if 'ocr_type' in locals() else 'unknown'}): {str(e)}"
        current_app.logger.error(error_log)
        return jsonify({
            'error': error_log,
            'code': 'UPLOAD_FAILED'
        }), 500

# 统一的任务状态查询接口
@api_bp.route('/file/status/<task_id>', methods=['GET'])
def unified_get_task_status(task_id):
    """
    获取任务状态
    
    路径参数:
        task_id: 任务ID
    查询参数:
        ocr_type: OCR处理类型，可选值为 standard (默认), llm, ollama
    """
    try:
        # 获取任务信息
        task_info = get_task_status(task_id)
        
        if task_info is None:
            return jsonify({
                'error': 'Task ID not found',
                'code': 'TASK_NOT_FOUND'
            }), 404
        
        # 确定处理类型
        ocr_type = request.args.get('ocr_type', 'standard').lower()
        if ocr_type not in ['standard', 'llm', 'ollama']:
            return jsonify({'error': f'不支持的OCR类型: {ocr_type}', 'code': 'INVALID_OCR_TYPE'}), 400
        
        # 对于Ollama类型，返回更详细的状态信息
        if ocr_type == 'ollama':
            status = task_info.get('status')
            
            if status == TaskStatus.PROCESSING.value:
                return jsonify({
                    "status": "processing",
                    "task_id": task_id
                })
            elif status == TaskStatus.COMPLETED.value:
                return jsonify({
                    "status": "completed",
                    "task_id": task_id,
                    "minio_url": task_info.get('result_url')
                })
            elif status == TaskStatus.FAILED.value:
                return jsonify({
                    "status": "failed",
                    "task_id": task_id,
                    "error": task_info.get('error')
                })
            elif status == TaskStatus.CANCELLED.value:
                return jsonify({
                    "status": "cancelled",
                    "task_id": task_id,
                    "error": task_info.get('error') or "任务已被取消"
                })
            else:
                return jsonify({
                    "status": "unknown",
                    "task_id": task_id
                })
        else:
            # 标准和LLM类型使用相同的响应格式
            return jsonify(task_info), 200
    except Exception as e:
        error_msg = f"获取任务状态失败 {task_id}: {str(e)}"
        current_app.logger.error(error_msg)
        return jsonify({
            "error": "服务器内部错误",
            "code": "INTERNAL_SERVER_ERROR"
        }), 500

# 统一的任务取消接口
@api_bp.route('/file/cancel/<task_id>', methods=['POST'])
def unified_cancel_task(task_id):
    """
    取消正在进行的OCR任务
    
    路径参数:
        task_id: 任务ID
    查询参数:
        ocr_type: OCR处理类型，可选值为 standard (默认), llm, ollama
    """
    try:
        # 确定处理类型
        ocr_type = request.args.get('ocr_type', 'standard').lower()
        if ocr_type not in ['standard', 'llm', 'ollama']:
            return jsonify({'error': f'不支持的OCR类型: {ocr_type}', 'code': 'INVALID_OCR_TYPE'}), 400
        
        # 获取任务状态
        task_info = get_task_status(task_id)
        
        if task_info is None:
            return jsonify({'error': 'Task ID not found', 'code': 'TASK_NOT_FOUND'}), 404
        
        # 检查任务是否可以取消
        if task_info['status'] != TaskStatus.PROCESSING.value:
            return jsonify({
                'error': '只能取消处理中的任务',
                'code': 'TASK_NOT_PROCESSING',
                'current_status': task_info['status']
            }), 400
        
        # 根据不同处理类型取消任务
        if ocr_type == 'llm':
            cancelled = llm_service.cancel_task(task_id)
            cancel_message = "LLM任务已被用户取消"
        elif ocr_type == 'ollama':
            cancelled = ollama_ocr_service.cancel_task(task_id)
            cancel_message = "Ollama OCR任务已被用户取消"
        else:  # standard
            cancelled = ocr_service.cancel_task(task_id)
            cancel_message = "任务已被用户取消"
        
        # 取消Celery任务
        celery.control.revoke(task_id, terminate=True)
        
        if cancelled:
            # 更新任务状态为已取消
            save_task_status(task_id, TaskStatus.CANCELLED.value, None, cancel_message)
            return jsonify({'message': cancel_message, 'ocr_type': ocr_type}), 200
        else:
            return jsonify({'error': f'任务取消失败', 'code': 'CANCEL_FAILED'}), 400
    except Exception as e:
        error_msg = f"取消任务失败 {task_id}: {str(e)}"
        current_app.logger.error(error_msg)
        return jsonify({
            "error": "服务器内部错误",
            "code": "INTERNAL_SERVER_ERROR"
        }), 500

# 为兼容性保留旧接口，同时避免URL冲突

# 标准OCR相关接口
@api_bp.route('/upload', methods=['POST'])
def legacy_upload_file():
    """旧版标准OCR上传接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，设置ocr_type=standard
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'standard'
    
    # 使用修改后的args调用统一上传函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_upload_file()

@api_bp.route('/status/<task_id>', methods=['GET'])
def legacy_get_task(task_id):
    """旧版标准OCR状态查询接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，设置ocr_type=standard
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'standard'
    
    # 使用修改后的args调用统一状态查询函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_get_task_status(task_id)

@api_bp.route('/cancel/<task_id>', methods=['POST'])
def legacy_cancel_task(task_id):
    """旧版标准OCR取消任务接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，设置ocr_type=standard
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'standard'
    
    # 使用修改后的args调用统一取消函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_cancel_task(task_id)

# LLM相关接口
@api_bp.route('/llm/upload', methods=['POST'])
def legacy_upload_file_llm():
    """旧版LLM上传接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，包含ocr_type=llm
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'llm'
    
    # 使用修改后的args调用统一上传函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_upload_file()

@api_bp.route('/llm/status/<task_id>', methods=['GET'])
def legacy_get_llm_task(task_id):
    """旧版LLM状态查询接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，包含ocr_type=llm
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'llm'
    
    # 使用修改后的args调用统一状态查询函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_get_task_status(task_id)

@api_bp.route('/llm/cancel/<task_id>', methods=['POST'])
def legacy_cancel_llm_task(task_id):
    """旧版LLM取消任务接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，包含ocr_type=llm
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'llm'
    
    # 使用修改后的args调用统一取消函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_cancel_task(task_id)

# Ollama OCR相关接口
@api_bp.route('/ocr/upload', methods=['POST'])
def legacy_upload_file_ollama_ocr():
    """旧版Ollama OCR上传接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，包含ocr_type=ollama
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'ollama'
    
    # 使用修改后的args调用统一上传函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_upload_file()

@api_bp.route('/ocr/status/<task_id>', methods=['GET'])
def legacy_get_ollama_ocr_task(task_id):
    """旧版Ollama OCR状态查询接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，包含ocr_type=ollama
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'ollama'
    
    # 使用修改后的args调用统一状态查询函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_get_task_status(task_id)

@api_bp.route('/ocr/cancel/<task_id>', methods=['POST'])
def legacy_cancel_ollama_ocr_task(task_id):
    """旧版Ollama OCR取消任务接口，代理到新接口"""
    from flask import request as current_request
    from werkzeug.datastructures import ImmutableMultiDict
    
    # 创建一个新的args字典，包含ocr_type=ollama
    args_dict = current_request.args.copy()
    args_dict['ocr_type'] = 'ollama'
    
    # 使用修改后的args调用统一取消函数
    current_request.args = ImmutableMultiDict(args_dict)
    return unified_cancel_task(task_id) 