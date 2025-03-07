import os
import logging
import requests
import base64
from typing import List, Dict, Any, Optional
import pdf2image
from threading import Lock

logger = logging.getLogger(__name__)

class OllamaOCRIntegration:
    """直接使用Ollama API的OCR实现，避免依赖问题"""
    
    def __init__(self, model_name="llama3.2-vision:11b", output_format="plain_text"):
        """
        初始化Ollama OCR集成服务
        
        参数:
            model_name: Ollama模型名称，默认为llama3.2-vision:11b
            output_format: 输出格式，保留做未来扩展
        """
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model_name = model_name
        self.output_format = output_format
        self._processing_tasks: Dict[str, bool] = {}  # 记录正在处理的任务
        self._lock = Lock()  # 用于线程安全的任务状态管理
        
        # 创建临时图片目录
        self.temp_image_dir = os.path.join('temp', 'ollama_images')
        os.makedirs(self.temp_image_dir, exist_ok=True)
        logger.info(f"创建Ollama临时图片目录: {self.temp_image_dir}")
        
        # 检查Ollama服务可用性
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name") for model in models]
                logger.info(f"Ollama服务可用，发现{len(models)}个模型")
                
                if self.model_name not in model_names:
                    logger.warning(f"模型 '{self.model_name}' 不可用，请使用 'ollama pull {self.model_name}' 下载")
            else:
                logger.warning(f"Ollama服务响应异常: {response.status_code}")
        except Exception as e:
            logger.error(f"Ollama服务检查失败: {str(e)}")
            logger.info("请确保Ollama服务已启动并可访问")
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """检查任务是否已被取消"""
        with self._lock:
            if task_id not in self._processing_tasks:
                return False
            return self._processing_tasks[task_id]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消正在处理的任务"""
        logger.info(f"尝试取消任务: {task_id}")
        with self._lock:
            if task_id not in self._processing_tasks:
                logger.warning(f"任务 {task_id} 不存在或已完成，无法取消")
                return False
            
            self._processing_tasks[task_id] = True
            logger.info(f"任务 {task_id} 已标记为取消")
            return True
    
    def start_task(self, task_id: str):
        """标记任务开始处理"""
        with self._lock:
            self._processing_tasks[task_id] = False
            logger.info(f"任务 {task_id} 开始处理")
    
    def finish_task(self, task_id: str):
        """标记任务完成处理"""
        with self._lock:
            if task_id in self._processing_tasks:
                del self._processing_tasks[task_id]
                logger.info(f"任务 {task_id} 处理完成")
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为base64格式"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"图片编码失败 {image_path}: {str(e)}")
            raise
    
    def process_image(self, image_path: str, task_id: str) -> str:
        """
        使用Ollama API直接处理单个图片
        
        参数:
            image_path: 图片路径
            task_id: 任务ID
            
        返回:
            str: 从图片中提取的文本
        """
        logger.info(f"处理图片 {image_path} 任务ID {task_id}")
        
        # 检查任务是否已取消
        if self._is_task_cancelled(task_id):
            logger.info(f"任务 {task_id} 已取消，停止处理图片")
            raise TaskCancelledException(f"任务 {task_id} 已取消")
        
        try:
            # 将图片编码为base64
            base64_image = self._encode_image_to_base64(image_path)
            
            # 构建Ollama API请求
            api_url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model_name,
                "prompt": "Extract all text from this image. Return only the extracted text without any explanations or additional comments.",
                "stream": False,
                "options": {
                    "temperature": 0.1
                },
                "images": [base64_image]
            }
            
            # 发送请求
            logger.info(f"发送请求到Ollama API，任务ID {task_id}")
            response = requests.post(api_url, json=payload, timeout=120)
            
            if response.status_code == 200:
                # 解析响应
                result = response.json()
                extracted_text = result.get("response", "")
                
                logger.info(f"图片处理成功，提取文本长度: {len(extracted_text)}")
                return extracted_text
            else:
                error_msg = f"Ollama API请求失败: HTTP {response.status_code}, {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"处理图片失败: {str(e)}")
            raise
    
    def split_pdf_to_images(self, pdf_path: str, task_id: str) -> List[str]:
        """将PDF分割为多个图片"""
        logger.info(f"将PDF分割为图片 {pdf_path} 任务ID {task_id}")
        
        # 检查任务是否已取消
        if self._is_task_cancelled(task_id):
            logger.info(f"任务 {task_id} 已取消，停止PDF分割")
            raise TaskCancelledException(f"任务 {task_id} 已取消")
        
        try:
            # 创建任务特定的临时目录
            task_image_dir = os.path.join(self.temp_image_dir, task_id)
            os.makedirs(task_image_dir, exist_ok=True)
            
            # 转换PDF为图片
            images = pdf2image.convert_from_path(pdf_path, dpi=300)
            image_paths = []
            
            # 保存每一页为图片
            for i, image in enumerate(images):
                # 检查任务是否已取消
                if self._is_task_cancelled(task_id):
                    logger.info(f"任务 {task_id} 已取消，停止PDF分割")
                    raise TaskCancelledException(f"任务 {task_id} 已取消")
                
                image_path = os.path.join(task_image_dir, f"page_{i+1}.png")
                image.save(image_path, "PNG")
                image_paths.append(image_path)
                
                logger.info(f"保存PDF第{i+1}页为图片: {image_path}")
            
            return image_paths
        
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"PDF分割失败: {str(e)}")
            raise
    
    def process_pdf(self, pdf_path: str, task_id: str) -> str:
        """处理PDF文件"""
        logger.info(f"开始处理PDF {pdf_path} 任务ID {task_id}")
        
        try:
            # 分割PDF为图片
            image_paths = self.split_pdf_to_images(pdf_path, task_id)
            
            # 处理所有图片并合并结果
            all_text = []
            
            for i, image_path in enumerate(image_paths):
                # 检查任务是否已取消
                if self._is_task_cancelled(task_id):
                    logger.info(f"任务 {task_id} 已取消，停止处理PDF图片")
                    raise TaskCancelledException(f"任务 {task_id} 已取消")
                
                logger.info(f"处理PDF第{i+1}页图片: {image_path}")
                try:
                    page_text = self.process_image(image_path, task_id)
                    all_text.append(f"--- 第{i+1}页 ---\n{page_text}\n")
                    logger.info(f"成功处理PDF第{i+1}页")
                except TaskCancelledException:
                    raise
                except Exception as e:
                    error_msg = f"处理第{i+1}页图片失败: {str(e)}"
                    logger.error(error_msg)
                    all_text.append(f"--- 第{i+1}页 (处理失败) ---\n{error_msg}\n")
            
            # 清理临时文件
            for image_path in image_paths:
                try:
                    os.remove(image_path)
                    logger.info(f"清理临时图片: {image_path}")
                except Exception as e:
                    logger.warning(f"清理临时图片失败 {image_path}: {str(e)}")
            
            # 尝试清理临时目录
            try:
                task_image_dir = os.path.join(self.temp_image_dir, task_id)
                os.rmdir(task_image_dir)
                logger.info(f"清理临时目录: {task_image_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败 {task_id}: {str(e)}")
            
            # 合并所有页面的文本
            return "\n".join(all_text)
            
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
            
            # 标记任务处理完成
            self.finish_task(task_id)
            
            return result
            
        except Exception as e:
            # 标记任务处理完成
            self.finish_task(task_id)
            
            # 重新抛出异常
            raise

# 创建服务实例
ollama_ocr_service = OllamaOCRIntegration()

class TaskCancelledException(Exception):
    """任务取消异常"""
    pass 