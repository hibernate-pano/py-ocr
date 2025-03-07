import os
import logging
from celery import shared_task
from celery.exceptions import Ignore

from app.models.task import TaskStatus, save_task_status
from app.services.llm_service import llm_service, TaskCancelledException
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_llm(self, task_id, file_path):
    """
    处理LLM多模态文本识别任务
    
    参数:
        task_id: 任务ID
        file_path: 文件路径
    """
    logger.info(f"开始LLM任务 {task_id}, 文件: {file_path}")
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"输入文件不存在: {file_path}"
            logger.error(error_msg)
            save_task_status(task_id, TaskStatus.FAILED.value, None, error_msg)
            raise FileNotFoundError(error_msg)
        
        # 处理文件进行LLM识别
        try:
            text_content = llm_service.process_file(file_path, task_id)
        except Exception as e:
            logger.error(f"LLM识别失败 {task_id}: {str(e)}")
            if self.request.retries < self.max_retries:
                logger.info(f"重试LLM识别 {task_id}, 第{self.request.retries+1}次")
                self.retry(exc=e, countdown=60 * (self.request.retries + 1))
            raise
        
        try:
            # 上传结果到MinIO
            object_name = f"llm_{task_id}.txt"
            result_url = minio_service.upload_text(object_name, text_content)
            
            # 更新任务状态为完成
            save_task_status(task_id, TaskStatus.COMPLETED.value, result_url, None)
            
            logger.info(f"LLM任务完成 {task_id}, 结果URL: {result_url}")
            
            # 成功完成后清理临时文件
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"临时文件已删除: {file_path}")
            except Exception as e:
                logger.warning(f"临时文件删除失败: {str(e)}")
            
            return result_url
            
        except Exception as e:
            logger.error(f"结果上传失败 {task_id}: {str(e)}")
            if self.request.retries < self.max_retries:
                logger.info(f"重试上传结果 {task_id}, 第{self.request.retries+1}次")
                self.retry(exc=e, countdown=60 * (self.request.retries + 1))
            raise
            
    except TaskCancelledException as e:
        logger.info(f"LLM任务已取消 {task_id}: {str(e)}")
        save_task_status(task_id, TaskStatus.CANCELLED.value, None, str(e))
        
        # 任务取消时清理临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"临时文件已删除: {file_path}")
        except Exception as ex:
            logger.warning(f"临时文件删除失败: {str(ex)}")
        
        raise Ignore()
        
    except Exception as e:
        logger.error(f"LLM任务失败 {task_id}: {str(e)}")
        save_task_status(task_id, TaskStatus.FAILED.value, None, str(e))
        
        if self.request.retries < self.max_retries:
            logger.info(f"重试LLM任务 {task_id}, 第{self.request.retries+1}次")
            # 不在重试前删除文件
            self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        else:
            # 达到最大重试次数后才清理文件
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"临时文件已删除: {file_path}")
            except Exception as ex:
                logger.warning(f"临时文件删除失败: {str(ex)}")
        
        raise 