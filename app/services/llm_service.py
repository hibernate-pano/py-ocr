import os
import base64
import logging
import requests
import json
from io import BytesIO
from PIL import Image
import traceback
from typing import Optional, Dict, Any, Union
from threading import Lock
from retry import retry

logger = logging.getLogger(__name__)

class TaskCancelledException(Exception):
    """表示任务已被取消的异常"""
    
    def __init__(self, message):
        super().__init__(message)


class LLMService:
    """多模态大模型服务类，提供图像文本识别功能"""
    
    def __init__(self):
        """初始化LLM服务"""
        self._processing_tasks = {}  # 记录正在处理的任务
        self._lock = Lock()  # 用于线程安全的任务状态管理
        self._api_key = None
        self._api_url = None
        
    def _load_config(self):
        """从环境变量加载配置"""
        self._api_key = os.getenv('SILICON_FLOW_API_KEY')
        self._api_url = os.getenv('SILICON_FLOW_API_URL', 'https://api.siliconflow.com/v1')
        
        if not self._api_key:
            raise ValueError("未配置硅基流动API密钥，请设置SILICON_FLOW_API_KEY环境变量")
            
        logger.info("硅基流动API配置加载成功")
    
    def _is_task_cancelled(self, task_id: str) -> bool:
        """
        检查任务是否已被取消
        
        参数:
            task_id: 任务ID
            
        返回:
            bool: 如果任务不存在或已被取消返回True，否则返回False
        """
        with self._lock:
            # 如果任务不存在，说明任务还未开始或已完成，不应该视为已取消
            if task_id not in self._processing_tasks:
                return False
            return self._processing_tasks[task_id]
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消指定的LLM任务
        
        参数:
            task_id: 任务ID
            
        返回:
            bool: 是否成功取消任务
        """
        with self._lock:
            if task_id in self._processing_tasks:
                self._processing_tasks[task_id] = True  # 标记任务为已取消
                logger.info(f"任务已标记为取消: {task_id}")
                return True
            logger.warning(f"尝试取消不存在的任务: {task_id}")
            return False
    
    def start_task(self, task_id: str):
        """
        开始追踪新任务
        
        参数:
            task_id: 任务ID
        """
        with self._lock:
            self._processing_tasks[task_id] = False  # False表示未取消
            logger.info(f"开始追踪任务: {task_id}")
    
    def finish_task(self, task_id: str):
        """
        完成任务，清理状态
        
        参数:
            task_id: 任务ID
        """
        with self._lock:
            if task_id in self._processing_tasks:
                self._processing_tasks.pop(task_id)
                logger.info(f"完成任务: {task_id}")
    
    @retry(tries=3, delay=2, backoff=2)
    def _call_llm_api(self, image_data: bytes) -> Dict[str, Any]:
        """
        调用硅基流动API进行图像识别
        
        参数:
            image_data: 图像二进制数据
            
        返回:
            Dict: API响应结果
        """
        if not self._api_key:
            self._load_config()
            
        # 将图像数据转换为Base64编码
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',  # 假设这是硅基流动的OCR专用模型
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': '请提取图像中的所有文本内容，保留原始格式。'
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/jpeg;base64,{base64_image}'
                            }
                        }
                    ]
                }
            ],
            'temperature': 0.1,  # 低温度值以获得更确定性的结果
            'max_tokens': 4000   # 足够大的值以容纳所有可能的文本
        }
        
        try:
            response = requests.post(
                f"{self._api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60  # 设置较长的超时时间
            )
            
            response.raise_for_status()  # 如果响应码不是2xx，抛出异常
            
            result = response.json()
            logger.info(f"硅基流动API响应状态码: {response.status_code}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"硅基流动API请求失败: {str(e)}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    def _extract_text_from_api_response(self, api_response: Dict[str, Any]) -> str:
        """
        从API响应中提取文本内容
        
        参数:
            api_response: API响应数据
            
        返回:
            str: 提取出的文本内容
        """
        try:
            # 假设API响应格式如下:
            # {
            #   "choices": [
            #     {
            #       "message": {
            #         "content": "提取的文本内容",
            #         ...
            #       },
            #       ...
            #     }
            #   ],
            #   ...
            # }
            text_content = api_response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if not text_content:
                logger.warning("API响应中没有找到文本内容")
                return "API响应中没有找到文本内容"
                
            return text_content
            
        except Exception as e:
            logger.error(f"提取文本内容失败: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return f"提取文本内容失败: {str(e)}"
    
    def process_image(self, image_path: str, task_id: str) -> str:
        """
        使用多模态大模型处理单张图片进行文本识别
        
        参数:
            image_path: 图片文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容（字符串类型）
        """
        try:
            logger.info(f"开始处理图片: {image_path}")
            
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止处理图片: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            # 验证图片文件是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 读取图片文件
            with open(image_path, 'rb') as f:
                image_data = f.read()
                
            # 调用硅基流动API
            api_response = self._call_llm_api(image_data)
            
            # 从API响应中提取文本
            text_content = self._extract_text_from_api_response(api_response)
            
            logger.info(f"多模态大模型识别完成，结果类型: {type(text_content)}")
            logger.info(f"识别结果长度: {len(text_content)}")
            
            return text_content
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"多模态大模型图片处理失败: {str(e)}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    def process_pdf(self, pdf_path: str, task_id: str) -> str:
        """
        使用多模态大模型处理PDF文件进行文本识别
        
        参数:
            pdf_path: PDF文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容（字符串类型）
        """
        try:
            logger.info(f"开始处理PDF: {pdf_path}")
            
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止处理PDF: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            # 验证PDF文件是否存在
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
            
            # 使用pdf2image将PDF转换为图片
            import pdf2image
            
            # 读取PDF文件
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
                
            # 将PDF转换为图像
            images = pdf2image.convert_from_bytes(
                pdf_content,
                dpi=300,
                fmt='jpeg'
            )
            
            if not images:
                raise ValueError("PDF转换后没有生成任何图片")
            
            all_text = []
            
            # 逐页处理
            for i, image in enumerate(images):
                logger.info(f"处理PDF第{i+1}页，共{len(images)}页")
                
                # 检查任务是否已取消
                if self._is_task_cancelled(task_id):
                    logger.info(f"任务已取消，停止处理PDF: {task_id}")
                    raise TaskCancelledException(f"任务已取消: {task_id}")
                
                # 将PIL图像转换为字节
                img_bytes = BytesIO()
                image.save(img_bytes, format='JPEG')
                img_bytes = img_bytes.getvalue()
                
                # 调用硅基流动API
                api_response = self._call_llm_api(img_bytes)
                
                # 从API响应中提取文本
                page_text = self._extract_text_from_api_response(api_response)
                
                # 添加页码标识
                all_text.append(f"===== 第 {i+1} 页 =====\n{page_text}\n")
            
            # 合并所有页面的文本
            full_text = "\n".join(all_text)
            logger.info(f"多模态大模型PDF处理完成，结果长度: {len(full_text)}")
            
            return full_text
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"多模态大模型PDF处理失败: {str(e)}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    def process_file(self, file_path: str, task_id: str) -> str:
        """
        根据文件类型选择合适的处理方法
        
        参数:
            file_path: 文件路径
            task_id: 任务ID
        
        返回:
            处理结果文本
        """
        self.start_task(task_id)
        
        try:
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # 根据文件扩展名选择处理方法
            if ext == '.pdf':
                result = self.process_pdf(file_path, task_id)
            elif ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif']:
                result = self.process_image(file_path, task_id)
            else:
                raise ValueError(f"不支持的文件类型: {ext}")
            
            self.finish_task(task_id)
            return result
            
        except Exception as e:
            self.finish_task(task_id)
            raise

# 创建单例实例
llm_service = LLMService() 