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

logger = logging.getLogger(__name__)

class TaskCancelledException(Exception):
    """表示任务已被取消的异常"""
    
    def __init__(self, message):
        super().__init__(message)


class LLMRequestException(Exception):
    """LLM API 请求异常"""
    
    def __init__(self, message, status_code=None, request_id=None):
        self.status_code = status_code
        self.request_id = request_id
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
        if not self._api_key:
            self._load_config()
            
        # 生成唯一请求ID以便日志追踪
        request_id = str(uuid.uuid4())
        logger.info(f"开始LLM API调用 [request_id: {request_id}]")
            
        # 将图像数据转换为Base64编码
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
            'X-Request-ID': request_id  # 添加请求ID到头信息
        }
        
        payload = {
            'model': 'Pro/Qwen/Qwen2-VL-7B-Instruct',  # 硅基流动的多模态模型
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
                f"{self._api_url}/chat/completions",
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
                
            # 检查PDF文件大小
            pdf_size_mb = len(pdf_content) / (1024 * 1024)
            logger.info(f"PDF文件大小: {pdf_size_mb:.2f} MB")
            
            # 大文件警告
            if pdf_size_mb > 20:
                logger.warning(f"PDF文件较大 ({pdf_size_mb:.2f} MB)，处理可能需要较长时间")
                
            # 将PDF转换为图像
            try:
                logger.info(f"开始将PDF转换为图像: {pdf_path}")
                images = pdf2image.convert_from_bytes(
                    pdf_content,
                    dpi=300,
                    fmt='jpeg'
                )
                logger.info(f"PDF转换完成，共生成{len(images)}页图像")
            except Exception as e:
                logger.error(f"PDF转换为图像失败: {str(e)}")
                logger.error(f"错误详情: {traceback.format_exc()}")
                raise
            
            if not images:
                raise ValueError("PDF转换后没有生成任何图片")
            
            all_text = []
            failed_pages = []
            
            # 逐页处理
            for i, image in enumerate(images):
                page_num = i + 1
                logger.info(f"处理PDF第{page_num}页，共{len(images)}页")
                
                # 检查任务是否已取消
                if self._is_task_cancelled(task_id):
                    logger.info(f"任务已取消，停止处理PDF: {task_id}")
                    raise TaskCancelledException(f"任务已取消: {task_id}")
                
                # 处理单页，使用重试机制
                max_page_retries = 3
                for retry_count in range(max_page_retries):
                    try:
                        # 将PIL图像转换为字节
                        img_bytes = BytesIO()
                        image.save(img_bytes, format='JPEG')
                        img_bytes = img_bytes.getvalue()
                        
                        # 调用硅基流动API
                        api_response = self._call_llm_api(img_bytes)
                        
                        # 从API响应中提取文本
                        page_text = self._extract_text_from_api_response(api_response)
                        
                        # 检查页面处理是否成功
                        if page_text and not page_text.startswith("API响应中没有找到文本内容") and not page_text.startswith("提取文本内容失败"):
                            # 添加页码标识
                            all_text.append(f"===== 第 {page_num} 页 =====\n{page_text}\n")
                            logger.info(f"成功处理PDF第{page_num}页")
                            break
                        else:
                            logger.warning(f"PDF第{page_num}页处理结果可能无效，尝试重试 ({retry_count+1}/{max_page_retries})")
                            if retry_count == max_page_retries - 1:  # 最后一次重试
                                logger.error(f"PDF第{page_num}页处理失败，已达到最大重试次数")
                                all_text.append(f"===== 第 {page_num} 页 (处理失败) =====\n{page_text}\n")
                                failed_pages.append(page_num)
                    except Exception as e:
                        logger.error(f"处理PDF第{page_num}页时发生错误: {str(e)}")
                        if retry_count == max_page_retries - 1:  # 最后一次重试
                            logger.error(f"PDF第{page_num}页处理失败，已达到最大重试次数")
                            all_text.append(f"===== 第 {page_num} 页 (处理失败) =====\n无法识别该页内容: {str(e)}\n")
                            failed_pages.append(page_num)
                        else:
                            logger.info(f"尝试重新处理PDF第{page_num}页 ({retry_count+1}/{max_page_retries})")
                            time.sleep(2 * (retry_count + 1))  # 指数退避
            
            # 合并所有页面的文本
            full_text = "\n".join(all_text)
            
            # 添加处理摘要
            total_pages = len(images)
            success_pages = total_pages - len(failed_pages)
            
            summary = f"""
处理摘要:
- 总页数: {total_pages}
- 成功页数: {success_pages}
- 失败页数: {len(failed_pages)}
"""
            if failed_pages:
                summary += f"- 失败页码: {', '.join(map(str, failed_pages))}\n"
                
            full_text = summary + "\n" + full_text
            
            logger.info(f"多模态大模型PDF处理完成，共处理{total_pages}页，成功{success_pages}页，结果长度: {len(full_text)}")
            
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