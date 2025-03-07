import os
import logging
import pytesseract
from PIL import Image
import pdf2image
import tempfile
from typing import List, Optional, Dict
from threading import Lock
from io import BytesIO

logger = logging.getLogger(__name__)

class OCRService:
    """OCR服务类，提供文本识别功能"""
    
    def __init__(self, languages='chi_sim+eng'):
        """
        初始化OCR服务
        
        参数:
            languages: Tesseract语言包，默认为中文简体+英文
        """
        self.languages = languages
        self._processing_tasks: Dict[str, bool] = {}  # 记录正在处理的任务
        self._lock = Lock()  # 用于线程安全的任务状态管理
        
        # 创建临时图片目录
        self.temp_image_dir = os.path.join('temp', 'images')
        os.makedirs(self.temp_image_dir, exist_ok=True)
        logger.info(f"创建临时图片目录: {self.temp_image_dir}")
    
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
        取消指定的OCR任务
        
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
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        对图片进行预处理，提高OCR识别效果
        
        参数:
            image: PIL Image对象
            
        返回:
            处理后的PIL Image对象
        """
        # 转换为灰度图
        image = image.convert('L')
        
        # TODO: 可以添加更多图像预处理步骤，如：
        # - 二值化
        # - 去噪
        # - 对比度增强
        # - 边缘检测等
        
        return image
    
    def process_image(self, image_path: str, task_id: str) -> str:
        """
        处理图片文件识别文本
        
        参数:
            image_path: 图片文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容（字符串类型）
        """
        try:
            logger.info(f"开始处理图片: {image_path}")
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                error_msg = f"图片文件不存在: {image_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # 检查文件是否可读
            try:
                with open(image_path, 'rb') as f:
                    image_content = f.read()
                    if not image_content:
                        raise ValueError("图片文件为空")
            except Exception as e:
                error_msg = f"图片文件无法读取: {str(e)}"
                logger.error(error_msg)
                raise
            
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止处理图片: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            try:
                # 使用BytesIO避免文件系统问题
                image_buffer = BytesIO(image_content)
                
                # 使用with语句确保图像文件正确关闭
                with Image.open(image_buffer) as image:
                    # 验证图片格式
                    if image.format not in ['PNG', 'JPEG', 'JPG', 'BMP', 'TIFF']:
                        raise ValueError(f"不支持的图片格式: {image.format}")
                    
                    # 图像预处理
                    processed_image = self.preprocess_image(image)
                    
                    # 再次检查任务是否已取消
                    if self._is_task_cancelled(task_id):
                        logger.info(f"任务已取消，停止OCR处理: {task_id}")
                        raise TaskCancelledException(f"任务已取消: {task_id}")
                    
                    # OCR识别
                    text = pytesseract.image_to_string(processed_image, lang=self.languages)
                    
                    # 确保返回的是字符串类型
                    if isinstance(text, bytes):
                        text = text.decode('utf-8')
                    elif not isinstance(text, str):
                        text = str(text)
                    
                    if not text.strip():
                        logger.warning(f"图片 {image_path} 没有识别出文本")
                    
                    logger.info(f"图片OCR处理完成: {image_path}")
                    return text
                    
            except TaskCancelledException:
                raise
            except Exception as e:
                error_msg = f"图片处理失败: {str(e)}"
                logger.error(error_msg)
                raise
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"图片OCR处理失败: {str(e)}")
            raise
    
    def split_pdf_to_images(self, pdf_path: str, task_id: str) -> List[str]:
        """
        将PDF文件切分为图片
        
        参数:
            pdf_path: PDF文件路径
            task_id: 任务ID
            
        返回:
            图片文件路径列表
        """
        try:
            logger.info(f"开始切分PDF: {pdf_path}")
            
            # 检查PDF文件是否存在
            if not os.path.exists(pdf_path):
                error_msg = f"PDF文件不存在: {pdf_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # 检查文件是否可读
            try:
                with open(pdf_path, 'rb') as f:
                    pdf_content = f.read()
                    if not pdf_content:
                        raise ValueError("PDF文件为空")
            except Exception as e:
                error_msg = f"PDF文件无法读取: {str(e)}"
                logger.error(error_msg)
                raise
            
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止切分PDF: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            # 为当前任务创建唯一的临时目录
            task_temp_dir = os.path.join(self.temp_image_dir, task_id)
            os.makedirs(task_temp_dir, exist_ok=True)
            logger.info(f"创建任务临时目录: {task_temp_dir}")
            
            # 将PDF转换为图片
            images = pdf2image.convert_from_bytes(
                pdf_content,
                dpi=300,    # 设置较高的DPI以获得更好的图像质量
                fmt='png',  # 指定输出格式
                output_folder=task_temp_dir,  # 指定输出目录
                paths_only=True,  # 返回文件路径而不是图片对象
                thread_count=2,  # 使用多线程加速处理
                use_pdftocairo=True  # 使用pdftocairo后端，通常更快更稳定
            )
            
            if not images:
                raise ValueError("PDF转换后没有生成任何图片")
            
            logger.info(f"PDF切分完成，共生成{len(images)}张图片")
            return images
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"PDF切分失败: {str(e)}")
            raise

    def process_pdf_images(self, image_paths: List[str], task_id: str) -> str:
        """
        处理PDF切分后的图片进行OCR识别
        
        参数:
            image_paths: 图片文件路径列表
            task_id: 任务ID
            
        返回:
            识别出的文本内容（字符串类型）
        """
        try:
            all_text = []
            # 对每一页分别进行OCR处理
            for i, image_path in enumerate(image_paths):
                # 检查任务是否已取消
                if self._is_task_cancelled(task_id):
                    logger.info(f"任务已取消，停止处理第{i+1}页: {task_id}")
                    raise TaskCancelledException(f"任务已取消: {task_id}")
                
                logger.info(f"处理第{i+1}页: {image_path}")
                
                # 验证图片文件是否存在
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"图片文件不存在: {image_path}")
                
                # 处理图片
                page_text = self.process_image(image_path, task_id)
                # 确保page_text是字符串类型
                if isinstance(page_text, bytes):
                    page_text = page_text.decode('utf-8')
                elif not isinstance(page_text, str):
                    page_text = str(page_text)
                
                if page_text.strip():  # 只添加非空文本
                    all_text.append(page_text)
            
            if not all_text:
                logger.warning("没有识别出任何文本")
                return ""
            
            # 确保返回的是字符串类型
            result = "\n\n".join(all_text)
            if isinstance(result, bytes):
                result = result.decode('utf-8')
            elif not isinstance(result, str):
                result = str(result)
            
            logger.info("OCR处理完成")
            return result
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"OCR处理失败: {str(e)}")
            raise

    def process_pdf(self, pdf_path: str, task_id: str) -> str:
        """
        处理PDF文件识别文本
        
        参数:
            pdf_path: PDF文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容（字符串类型）
        """
        try:
            # 第一步：切分PDF为图片
            image_paths = self.split_pdf_to_images(pdf_path, task_id)
            
            # 第二步：处理图片进行OCR识别
            result = self.process_pdf_images(image_paths, task_id)
            
            return result
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"PDF处理失败: {str(e)}")
            raise
        finally:
            # 清理任务临时目录
            try:
                task_temp_dir = os.path.join(self.temp_image_dir, task_id)
                if os.path.exists(task_temp_dir):
                    for file in os.listdir(task_temp_dir):
                        try:
                            os.remove(os.path.join(task_temp_dir, file))
                        except Exception as e:
                            logger.warning(f"删除临时文件失败: {str(e)}")
                    os.rmdir(task_temp_dir)
                    logger.info(f"已清理任务临时目录: {task_temp_dir}")
            except Exception as e:
                logger.warning(f"清理任务临时目录失败: {str(e)}")
    
    def process_file(self, file_path: str, task_id: str) -> str:
        """
        处理文件，自动判断类型并进行OCR处理
        
        参数:
            file_path: 文件路径
            task_id: 任务ID
            
        返回:
            识别出的文本内容
        """
        try:
            # 开始追踪任务
            self.start_task(task_id)
            
            # 获取文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            # 根据文件类型进行处理
            if ext == '.pdf':
                return self.process_pdf(file_path, task_id)
            elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
                return self.process_image(file_path, task_id)
            else:
                error_msg = f"不支持的文件类型: {ext}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        finally:
            # 完成任务，清理状态
            self.finish_task(task_id)

class TaskCancelledException(Exception):
    """任务取消异常"""
    pass

# 创建单例实例
ocr_service = OCRService() 