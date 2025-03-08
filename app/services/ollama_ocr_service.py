import os
import logging
import requests
import base64
from typing import List, Dict, Any, Optional
import pdf2image
from threading import Lock
import time
from io import BytesIO

from app.utils.pdf_utils import PDFProcessor, TaskCancelledException

logger = logging.getLogger(__name__)

class OllamaOCRIntegration:
    """Ollama OCR集成服务，使用Ollama本地多模态模型进行OCR识别"""
    
    def __init__(self, model_name="llama3.2-vision:11b", output_format="plain_text"):
        """
        初始化Ollama OCR集成服务
        
        参数:
            model_name: 使用的Ollama模型名称
            output_format: 输出格式 (plain_text, markdown, json, structured, key_value)
        """
        # 从环境变量获取配置
        self.base_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = os.environ.get('OLLAMA_MODEL', model_name)
        self.output_format = os.environ.get('OLLAMA_OUTPUT_FORMAT', output_format)
        self.timeout = int(os.environ.get('OLLAMA_TIMEOUT', 120))
        
        # 任务处理状态跟踪
        self._processing_tasks = set()
        
        # 临时目录
        self.temp_image_dir = os.path.join(os.getcwd(), 'temp', 'ollama_images')
        os.makedirs(self.temp_image_dir, exist_ok=True)
        
        # 提示词模板
        self.prompt_templates = {
            "plain_text": "从图片中提取所有文本内容，按原始布局排列。",
            "markdown": "从图片中提取所有文本内容，使用Markdown格式保留原始布局。用**加粗**表示标题，用表格表示表格内容。",
            "json": "从图片中提取所有文本内容，并以JSON格式返回，包含标题、段落、表格等结构信息。",
            "structured": "从图片中提取所有结构化内容，识别标题、段落、表格、列表等元素，并保持原始布局。",
            "key_value": "从图片中提取所有键值对信息，格式为'键: 值'的形式。"
        }
        
        logger.info(f"Ollama OCR服务初始化完成，模型: {self.model}, 输出格式: {self.output_format}")
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """
        检查任务是否已取消
        
        参数:
            task_id: 任务ID
            
        返回:
            如果任务已取消，返回True，否则返回False
        """
        return task_id not in self._processing_tasks
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        参数:
            task_id: 要取消的任务ID
            
        返回:
            如果任务取消成功或任务已不存在，返回True
        """
        if task_id in self._processing_tasks:
            self._processing_tasks.remove(task_id)
            logger.info(f"任务已取消: {task_id}")
            return True
        return False
    
    def start_task(self, task_id: str):
        """
        标记任务开始处理
        
        参数:
            task_id: 任务ID
        """
        self._processing_tasks.add(task_id)
        logger.info(f"任务开始处理: {task_id}")
    
    def finish_task(self, task_id: str):
        """
        标记任务处理完成
        
        参数:
            task_id: 任务ID
        """
        if task_id in self._processing_tasks:
            self._processing_tasks.remove(task_id)
            logger.info(f"任务处理完成: {task_id}")
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64格式"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def process_image(self, image_path: str, task_id: str) -> str:
        """
        处理单张图片
        
        参数:
            image_path: 图片路径
            task_id: 任务ID
            
        返回:
            提取的文本内容
        """
        try:
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务 {task_id} 已取消，停止处理图片")
                raise TaskCancelledException(f"任务 {task_id} 已取消")
            
            logger.info(f"使用Ollama处理图片 {image_path}")
            
            # 将图片编码为base64
            image_b64 = self._encode_image_to_base64(image_path)
            
            # 构建提示词
            prompt = self.prompt_templates.get(
                self.output_format, 
                self.prompt_templates["plain_text"]
            )
            
            # 构建请求数据
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            }
            
            # 发送请求到Ollama API
            logger.info(f"发送请求到Ollama API，使用模型: {self.model}")
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            # 检查响应
            response.raise_for_status()
            result = response.json()
            
            # 从响应中提取文本
            extracted_text = result.get("response", "")
            
            logger.info(f"Ollama处理完成，提取文本长度: {len(extracted_text)}")
            return extracted_text
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"处理图片失败: {str(e)}")
            raise
    
    def split_pdf_to_images(self, pdf_path: str, task_id: str) -> List[str]:
        """将PDF分割为多个图片"""
        logger.info(f"将PDF分割为图片 {pdf_path} 任务ID {task_id}")
        
        # 为当前任务创建唯一的临时目录
        task_temp_dir = os.path.join(self.temp_image_dir, task_id)
        os.makedirs(task_temp_dir, exist_ok=True)
        
        # 使用共享PDF处理器
        return PDFProcessor.split_pdf_to_images(
            pdf_path=pdf_path,
            output_dir=task_temp_dir,
            task_id=task_id,
            dpi=300,
            fmt='png',
            cancel_check_func=self._is_task_cancelled,
            return_paths=True,
            thread_count=2,
            use_pdftocairo=True
        )
    
    def process_pdf(self, pdf_path: str, task_id: str) -> str:
        """
        处理PDF文件
        
        参数:
            pdf_path: PDF文件路径
            task_id: 任务ID
            
        返回:
            提取的文本内容
        """
        try:
            logger.info(f"开始处理PDF {pdf_path} 任务ID {task_id}")
            
            # 第一步：将PDF分割为图片
            image_paths = self.split_pdf_to_images(pdf_path, task_id)
            logger.info(f"PDF分割完成，共{len(image_paths)}页")
            
            # 使用共享处理器处理图片
            result = PDFProcessor.process_pdf_images(
                image_paths=image_paths,
                task_id=task_id,
                processor_func=self.process_image,
                cancel_check_func=self._is_task_cancelled
            )
            
            # 清理临时文件
            task_temp_dir = os.path.join(self.temp_image_dir, task_id)
            try:
                for image_path in image_paths:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                
                if os.path.exists(task_temp_dir):
                    os.rmdir(task_temp_dir)
                    logger.info(f"已清理任务临时目录: {task_temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")
            
            return result
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"处理PDF失败: {str(e)}")
            raise
    
    def process_file(self, file_path: str, task_id: str) -> str:
        """处理文件并提取文本"""
        logger.info(f"处理文件 {file_path} 任务ID {task_id}")
        
        # 标记任务开始处理
        self.start_task(task_id)
        
        try:
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # 处理结果
            result = ""
            
            # 根据文件类型进行处理
            if ext == '.pdf':
                result = self.process_pdf(file_path, task_id)
            elif ext in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp']:
                result = self.process_image(file_path, task_id)
            else:
                error_msg = f"不支持的文件类型: {ext}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 返回结果
            logger.info(f"文件处理完成，结果长度: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"处理文件失败: {str(e)}")
            raise
        finally:
            # 标记任务完成
            self.finish_task(task_id)

# 创建单例实例
ollama_ocr_service = OllamaOCRIntegration() 