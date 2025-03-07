import os
import logging
from celery import shared_task
from celery.exceptions import Ignore

from app.models.task import TaskStatus, save_task_status
from app.services.ollama_ocr_service import ollama_ocr_service, TaskCancelledException
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_ollama_ocr(self, task_id, file_path):
    """
    处理Ollama OCR任务，使用GitHub的Ollama-OCR项目
    
    参数:
        task_id: 任务ID
        file_path: 文件路径
    """
    logger.info(f"开始Ollama OCR任务 {task_id}, 文件: {file_path}")
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"输入文件不存在: {file_path}"
            logger.error(error_msg)
            save_task_status(task_id, TaskStatus.FAILED.value, None, error_msg)
            raise FileNotFoundError(error_msg)
        
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # 根据文件类型进行处理
        try:
            # 使用Ollama-OCR集成服务处理文件
            text_content = ollama_ocr_service.process_file(file_path, task_id)
            
            # 保存结果到MinIO
            text_filename = f"{task_id}.txt"
            minio_url = minio_service.upload_text(text_filename, text_content)
            
            # 更新任务状态为已完成
            save_task_status(task_id, TaskStatus.COMPLETED.value, minio_url)
            
            logger.info(f"Ollama OCR任务 {task_id} 已完成")
            return {"task_id": task_id, "status": "completed", "minio_url": minio_url}
            
        except TaskCancelledException:
            logger.info(f"Ollama OCR任务 {task_id} 已被取消")
            save_task_status(task_id, TaskStatus.CANCELLED.value, None, "任务已被用户取消")
            return {"task_id": task_id, "status": "cancelled", "error": "任务已被用户取消"}
            
        except Exception as e:
            logger.error(f"Ollama OCR处理失败 {task_id}: {str(e)}")
            # 尝试重试任务
            if self.request.retries < self.max_retries:
                logger.info(f"正在重试Ollama OCR任务 {task_id}，第 {self.request.retries + 1} 次")
                self.retry(countdown=60, exc=e)
            else:
                error_msg = f"Ollama OCR处理失败: {str(e)}"
                save_task_status(task_id, TaskStatus.FAILED.value, None, error_msg)
                logger.error(f"Ollama OCR任务 {task_id} 达到最大重试次数，标记为失败")
                return {"task_id": task_id, "status": "failed", "error": error_msg}
    
    except FileNotFoundError as e:
        # 文件不存在，直接标记失败，不重试
        error_msg = str(e)
        save_task_status(task_id, TaskStatus.FAILED.value, None, error_msg)
        logger.error(f"Ollama OCR文件不存在 {task_id}: {error_msg}")
        return {"task_id": task_id, "status": "failed", "error": error_msg}
    
    except Exception as e:
        # 任务处理过程中的未知异常
        error_msg = f"Ollama OCR任务异常: {str(e)}"
        save_task_status(task_id, TaskStatus.FAILED.value, None, error_msg)
        logger.error(f"Ollama OCR任务异常 {task_id}: {error_msg}")
        return {"task_id": task_id, "status": "failed", "error": error_msg}
    
    finally:
        # 清理临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"临时文件已删除: {file_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败 {file_path}: {str(e)}") 