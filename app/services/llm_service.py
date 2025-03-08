import os
import base64
import logging
import requests
import json
import time
import uuid
import random
from io import BytesIO
from PIL import Image
import traceback
from typing import Optional, Dict, Any, Union
from threading import Lock
from retry import retry

from app.utils.pdf_utils import PDFProcessor, TaskCancelledException

logger = logging.getLogger(__name__)

class LLMRequestException(Exception):
    """LLM请求异常，包含HTTP状态码和请求ID"""
    
    def __init__(self, message, status_code=None, request_id=None):
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        super().__init__(self.message)


class LLMService:
    """多模态大模型服务，提供图片文本识别功能"""
    
    def __init__(self):
        """初始化LLM服务"""
        # 任务处理状态跟踪
        self._processing_tasks = set()
        # 临时文件目录
        self.temp_image_dir = os.path.join(os.getcwd(), 'temp', 'llm_images')
        os.makedirs(self.temp_image_dir, exist_ok=True)
        
        # 加载配置
        self._load_config()
        
        logger.info("LLM服务初始化完成")
    
    def _load_config(self):
        """加载配置"""
        # 从环境变量获取API密钥和URL
        self.api_key = os.environ.get('SILICON_FLOW_API_KEY')
        self.api_url = os.environ.get('SILICON_FLOW_API_URL', 'https://api.siliconflow.com/v1')
        
        # 检查API密钥是否存在
        if not self.api_key:
            logger.warning("API密钥未设置，LLM功能可能无法正常工作")
    
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
            如果任务取消成功或任务已不存在，返回True，
            如果任务不在处理中，返回False
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
    
    @retry(
        tries=5,  # 增加尝试次数
        delay=2,
        backoff=2,
        max_delay=30,  # 最大延迟30秒
        exceptions=(
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            json.JSONDecodeError,
            LLMRequestException,
        )
    )
    def _call_llm_api(self, image_data: bytes) -> Dict[str, Any]:
        """
        调用硅基流动API进行图像识别
        
        参数:
            image_data: 图像二进制数据
            
        返回:
            Dict: API响应结果
        """
        if not self.api_key:
            self._load_config()
            
        # 生成唯一请求ID以便日志追踪
        request_id = str(uuid.uuid4())
        logger.info(f"开始LLM API调用 [request_id: {request_id}]")
            
        # 将图像数据转换为Base64编码
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-Request-ID': request_id  # 添加请求ID到头信息
        }
        
        payload = {
            # 'model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',  # 硅基流动的多模态模型
            'model': 'Qwen/Qwen2-VL-72B-Instruct',  
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
        
        start_time = time.time()
        
        try:
            # 增加超时参数，分别设置连接超时和读取超时
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=(10, 120),  # 连接超时10秒，读取超时120秒
            )
            
            # 记录响应时间
            elapsed_time = time.time() - start_time
            logger.info(f"LLM API响应时间: {elapsed_time:.2f}秒 [request_id: {request_id}]")
            
            # 检查状态码
            if response.status_code != 200:
                error_msg = f"API返回非200状态码: {response.status_code}"
                logger.error(f"{error_msg} [request_id: {request_id}]")
                
                # 尝试获取更多错误信息
                try:
                    error_details = response.json()
                    error_msg = f"{error_msg}, 详情: {json.dumps(error_details)}"
                except:
                    pass
                
                # 分类HTTP错误以便于重试逻辑
                if response.status_code >= 500:
                    logger.error(f"服务器错误，将重试 [request_id: {request_id}]")
                    raise LLMRequestException(error_msg, status_code=response.status_code, request_id=request_id)
                elif response.status_code == 429:
                    logger.error(f"请求频率限制，将重试 [request_id: {request_id}]")
                    # 对于频率限制错误，增加随机等待时间
                    time.sleep(5 + random.uniform(0, 5))
                    raise LLMRequestException(error_msg, status_code=response.status_code, request_id=request_id)
                elif response.status_code >= 400:
                    logger.error(f"客户端错误，状态码: {response.status_code} [request_id: {request_id}]")
                    if response.status_code in [401, 403]:  # 认证错误
                        logger.critical(f"API认证错误，请检查API密钥 [request_id: {request_id}]")
                    raise LLMRequestException(error_msg, status_code=response.status_code, request_id=request_id)
            
            # 尝试解析JSON响应
            try:
                result = response.json()
                
                # 验证响应内容
                if "choices" not in result or not result["choices"] or "message" not in result["choices"][0]:
                    error_msg = "API响应格式无效，缺少预期字段"
                    logger.error(f"{error_msg} [request_id: {request_id}]")
                    raise LLMRequestException(error_msg, request_id=request_id)
                
                logger.info(f"成功获取API响应 [request_id: {request_id}]")
                return result
                
            except json.JSONDecodeError:
                error_msg = "API响应不是有效的JSON格式"
                logger.error(f"{error_msg} [request_id: {request_id}]")
                logger.error(f"响应内容: {response.text[:1000]} [request_id: {request_id}]")
                raise LLMRequestException(error_msg, request_id=request_id)
                
        except requests.exceptions.Timeout:
            error_msg = f"API请求超时 (连接超时10秒，读取超时120秒) [request_id: {request_id}]"
            logger.error(error_msg)
            raise
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"API连接错误 [request_id: {request_id}]: {str(e)}"
            logger.error(error_msg)
            raise
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API请求异常 [request_id: {request_id}]: {str(e)}"
            logger.error(error_msg)
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
            
        except Exception as e:
            error_msg = f"API调用过程中出现未预期的异常 [request_id: {request_id}]: {str(e)}"
            logger.error(error_msg)
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
            # 获取请求ID（如果有的话）
            request_id = api_response.get('request_id', 'unknown')
            
            # 检查必要的字段是否存在
            if not isinstance(api_response, dict):
                logger.error(f"API响应不是字典类型 [request_id: {request_id}]")
                return "API响应格式无效，无法提取文本内容"
                
            # 提取文本内容
            if "choices" not in api_response or not api_response["choices"]:
                logger.error(f"API响应中没有choices字段 [request_id: {request_id}]")
                logger.error(f"API响应内容: {json.dumps(api_response)[:1000]}")
                return "API响应中没有找到文本内容"
                
            first_choice = api_response["choices"][0]
            if "message" not in first_choice:
                logger.error(f"API响应中没有message字段 [request_id: {request_id}]")
                logger.error(f"响应choices内容: {json.dumps(first_choice)[:1000]}")
                return "API响应中没有找到文本内容"
                
            message = first_choice["message"]
            if "content" not in message or not message["content"]:
                logger.error(f"API响应中没有content字段 [request_id: {request_id}]")
                logger.error(f"响应message内容: {json.dumps(message)[:1000]}")
                return "API响应中没有找到文本内容"
                
            text_content = message["content"]
            
            # 确保返回的是字符串类型
            if not isinstance(text_content, str):
                logger.warning(f"API响应中content字段不是字符串类型，尝试转换 [request_id: {request_id}]")
                text_content = str(text_content)
            
            # 记录提取结果
            if not text_content:
                logger.warning(f"API响应中提取到的文本内容为空 [request_id: {request_id}]")
                return "API响应中提取到的文本内容为空"
                
            content_length = len(text_content)
            logger.info(f"成功从API响应中提取文本内容，长度: {content_length} [request_id: {request_id}]")
            
            # 如果文本内容过短，可能提取失败
            if content_length < 10 and "error" in text_content.lower():
                logger.warning(f"提取的文本内容可能是错误信息 [request_id: {request_id}]: {text_content}")
                
            return text_content
            
        except Exception as e:
            logger.error(f"提取文本内容失败: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            logger.error(f"API响应内容: {str(api_response)[:1000]}")
            return f"提取文本内容失败: {str(e)}"
    
    def process_image(self, image_path: str, task_id: str) -> str:
        """
        使用LLM处理图片
        
        参数:
            image_path: 图片文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容
        """
        try:
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止处理图片: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            logger.info(f"开始LLM处理图片: {image_path}")
            
            # 验证图片文件是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图片文件不存在: {image_path}")
            
            # 读取图片文件
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()
            
            # 调用LLM API
            logger.info(f"调用LLM API处理图片: {image_path}")
            start_time = time.time()
            api_response = self._call_llm_api(image_data)
            elapsed_time = time.time() - start_time
            logger.info(f"LLM API调用完成，耗时: {elapsed_time:.2f}秒")
            
            # 从API响应中提取文本
            text = self._extract_text_from_api_response(api_response)
            logger.info(f"从API响应中提取文本完成，长度: {len(text)}")
            
            return text
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"LLM处理图片失败: {str(e)}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise

    def process_pdf(self, pdf_path: str, task_id: str) -> str:
        """
        使用LLM处理PDF文件
        
        参数:
            pdf_path: PDF文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容
        """
        try:
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止处理PDF: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            logger.info(f"开始LLM处理PDF: {pdf_path}")
            
            # 验证PDF文件是否存在
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
            
            # 为当前任务创建唯一的临时目录
            task_temp_dir = os.path.join(self.temp_image_dir, task_id)
            os.makedirs(task_temp_dir, exist_ok=True)
            
            # 使用共享PDF处理器将PDF切分为图片
            logger.info(f"开始切分PDF文件: {pdf_path}")
            images = PDFProcessor.split_pdf_to_images(
                pdf_path=pdf_path,
                output_dir=task_temp_dir,
                task_id=task_id,
                dpi=300,
                fmt='jpeg',
                cancel_check_func=self._is_task_cancelled,
                return_paths=True,
                thread_count=2,
                use_pdftocairo=True
            )
            logger.info(f"PDF切分完成，共{len(images)}页")
            
            # 使用process_image方法处理每个图片，并收集结果
            all_text = []
            failed_pages = []
            
            for i, image_path in enumerate(images):
                # 检查任务是否已取消
                if self._is_task_cancelled(task_id):
                    logger.info(f"任务已取消，停止处理PDF: {task_id}")
                    raise TaskCancelledException(f"任务已取消: {task_id}")
                
                page_num = i + 1
                logger.info(f"处理PDF第{page_num}页，共{len(images)}页")
                
                try:
                    page_text = self.process_image(image_path, task_id)
                    all_text.append(f"--- 第{page_num}页 ---\n{page_text}")
                    logger.info(f"处理PDF第{page_num}页完成，文本长度: {len(page_text)}")
                except Exception as e:
                    logger.error(f"处理PDF第{page_num}页失败: {str(e)}")
                    failed_pages.append(page_num)
                    all_text.append(f"--- 第{page_num}页（处理失败）---")
                
                # 清理临时图片文件
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        logger.debug(f"删除临时图片文件: {image_path}")
                except Exception as e:
                    logger.warning(f"删除临时图片文件失败: {image_path}, {str(e)}")
            
            # 合并所有页面的文本
            combined_text = "\n\n".join(all_text)
            
            # 添加处理摘要
            if failed_pages:
                footer = f"\n\n--- 处理摘要 ---\n总页数: {len(images)}\n成功页数: {len(images) - len(failed_pages)}\n失败页数: {len(failed_pages)}\n失败页码: {', '.join(map(str, failed_pages))}"
            else:
                footer = f"\n\n--- 处理摘要 ---\n总页数: {len(images)}\n所有页面处理成功"
                
            combined_text += footer
            
            # 清理任务临时目录
            try:
                if os.path.exists(task_temp_dir):
                    os.rmdir(task_temp_dir)
                    logger.info(f"删除临时目录: {task_temp_dir}")
            except Exception as e:
                logger.warning(f"删除临时目录失败: {task_temp_dir}, {str(e)}")
            
            return combined_text
            
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
            
            return result
            
        except Exception as e:
            logger.error(f"处理文件失败: {str(e)}")
            raise
        finally:
            # 无论处理成功还是失败，都标记任务完成
            self.finish_task(task_id)

# 创建单例实例
llm_service = LLMService() 