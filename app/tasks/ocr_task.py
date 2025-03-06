import os
import logging
from celery import shared_task

from app.models.task import TaskStatus, save_task_status
from app.services.ocr_service import ocr_service
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_ocr(self, task_id, file_path):
    """
    处理OCR任务
    
    参数:
        task_id: 任务ID
        file_path: 文件路径
    """
    logger.info(f"开始OCR任务 {task_id}, 文件: {file_path}")
    
    try:
        # 执行OCR识别
        text_content = ocr_service.process_file(file_path)
        
        # 上传结果到MinIO
        object_name = f"{task_id}.txt"
        result_url = minio_service.upload_text(object_name, text_content)
        
        # 更新任务状态为完成
        save_task_status(task_id, TaskStatus.COMPLETED.value, result_url, None)
        
        logger.info(f"OCR任务完成 {task_id}, 结果URL: {result_url}")
        
        # 清理临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"临时文件已删除: {file_path}")
        except Exception as e:
            logger.warning(f"临时文件删除失败: {str(e)}")
        
        return result_url
    except Exception as e:
        logger.error(f"OCR任务失败 {task_id}: {str(e)}")
        
        # 更新任务状态为失败
        save_task_status(task_id, TaskStatus.FAILED.value, None, str(e))
        
        # 重试任务
        if self.request.retries < self.max_retries:
            logger.info(f"重试OCR任务 {task_id}, 第{self.request.retries+1}次")
            self.retry(exc=e, countdown=60 * (self.request.retries + 1))  # 指数退避策略
        
        # 清理临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"临时文件已删除: {file_path}")
        except Exception as ex:
            logger.warning(f"临时文件删除失败: {str(ex)}")
        
        # 重新抛出异常
        raise 