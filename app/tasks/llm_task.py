import os
import logging
import time
from celery import shared_task
from celery.exceptions import Ignore

from app.models.task import TaskStatus, save_task_status
from app.services.llm_service import llm_service, TaskCancelledException, LLMRequestException
from app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=300, rate_limit="10/m")
def process_llm(self, task_id, file_path):
    """
    处理LLM多模态文本识别任务
    
    参数:
        task_id: 任务ID
        file_path: 文件路径
    """
    logger.info(f"开始LLM任务 {task_id}, 文件: {file_path}")
    start_time = time.time()
    
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"输入文件不存在: {file_path}"
            logger.error(error_msg)
            save_task_status(task_id, TaskStatus.FAILED.value, None, error_msg)
            raise FileNotFoundError(error_msg)
        
        # 处理文件进行LLM识别
        try:
            logger.info(f"开始LLM识别 {task_id}")
            text_content = llm_service.process_file(file_path, task_id)
            logger.info(f"LLM识别完成 {task_id}, 结果长度: {len(text_content)}")
        except LLMRequestException as e:
            # 特定处理API请求异常
            retry_delay = min(60 * (self.request.retries + 1), 300)  # 最大延迟5分钟
            
            # 根据错误状态码调整重试策略
            if hasattr(e, 'status_code'):
                if e.status_code == 429:  # 频率限制
                    retry_delay = 120 + (60 * self.request.retries)  # 更长的延迟
                    logger.warning(f"遇到API频率限制，将在{retry_delay}秒后重试 {task_id}")
                elif e.status_code >= 500:  # 服务器错误
                    logger.warning(f"遇到API服务器错误，将在{retry_delay}秒后重试 {task_id}")
                elif e.status_code in [401, 403]:  # 认证错误
                    logger.critical(f"API认证错误，请检查API密钥: {str(e)}")
                    save_task_status(task_id, TaskStatus.FAILED.value, None, f"API认证失败: {str(e)}")
                    raise  # 不重试认证错误
            
            logger.error(f"LLM识别失败 {task_id}: {str(e)}")
            if self.request.retries < self.max_retries:
                logger.info(f"重试LLM识别 {task_id}, 第{self.request.retries+1}次, 延迟{retry_delay}秒")
                self.retry(exc=e, countdown=retry_delay)
            else:
                logger.error(f"达到最大重试次数，LLM识别任务失败 {task_id}")
                raise
        except Exception as e:
            logger.error(f"LLM识别失败 {task_id}: {str(e)}")
            if self.request.retries < self.max_retries:
                retry_delay = 60 * (self.request.retries + 1)
                logger.info(f"重试LLM识别 {task_id}, 第{self.request.retries+1}次, 延迟{retry_delay}秒")
                self.retry(exc=e, countdown=retry_delay)
            raise
        
        try:
            # 上传结果到MinIO
            object_name = f"llm_{task_id}.txt"
            logger.info(f"开始上传结果到MinIO: {object_name}")
            result_url = minio_service.upload_text(object_name, text_content)
            
            # 更新任务状态为完成
            elapsed_time = time.time() - start_time
            logger.info(f"LLM任务完成 {task_id}, 处理时间: {elapsed_time:.2f}秒, 结果URL: {result_url}")
            save_task_status(task_id, TaskStatus.COMPLETED.value, result_url, None)
            
            # 成功完成后清理临时文件
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"临时文件已删除: {file_path}")
            except Exception as e:
                logger.warning(f"临时文件删除失败: {str(e)}")
            
            return {
                'task_id': task_id,
                'status': TaskStatus.COMPLETED.value,
                'result_url': result_url,
                'processing_time': f"{elapsed_time:.2f}秒"
            }
            
        except Exception as e:
            logger.error(f"结果上传失败 {task_id}: {str(e)}")
            if self.request.retries < self.max_retries:
                retry_delay = 60 * (self.request.retries + 1)
                logger.info(f"重试上传结果 {task_id}, 第{self.request.retries+1}次, 延迟{retry_delay}秒")
                self.retry(exc=e, countdown=retry_delay)
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
        elapsed_time = time.time() - start_time
        error_msg = f"LLM任务失败 {task_id} (耗时: {elapsed_time:.2f}秒): {str(e)}"
        logger.error(error_msg)
        save_task_status(task_id, TaskStatus.FAILED.value, None, str(e))
        
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (self.request.retries + 1)
            logger.info(f"重试LLM任务 {task_id}, 第{self.request.retries+1}次, 延迟{retry_delay}秒")
            # 不在重试前删除文件
            self.retry(exc=e, countdown=retry_delay)
        else:
            # 达到最大重试次数后才清理文件
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"临时文件已删除: {file_path}")
            except Exception as ex:
                logger.warning(f"临时文件删除失败: {str(ex)}")
        
        raise 