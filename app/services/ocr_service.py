import os
import logging
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
import pdf2image
import tempfile
from typing import List, Optional, Dict
from threading import Lock
from io import BytesIO
import traceback

from app.utils.pdf_utils import PDFProcessor, TaskCancelledException

logger = logging.getLogger(__name__)

class OCRService:
    """OCR服务，处理文档图像并提取文本"""
    
    def __init__(self, languages='chi_sim+eng'):
        """
        初始化OCR服务
        
        参数:
            languages: 语言设置，默认为中文+英文
        """
        self.languages = languages
        # 任务处理状态跟踪
        self._processing_tasks = set()
        # 临时文件目录
        self.temp_image_dir = os.path.join(os.getcwd(), 'temp', 'images')
        os.makedirs(self.temp_image_dir, exist_ok=True)
        
        logger.info(f"OCR服务初始化完成，语言设置: {languages}")
    
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
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        预处理图像以提高OCR识别效果
        
        参数:
            image: 原始图像
            
        返回:
            预处理后的图像
        """
        try:
            # 转换为灰度图
            gray_image = image.convert('L')
            
            # 应用轻微的模糊来减少噪点
            denoised = gray_image.filter(ImageFilter.GaussianBlur(radius=1))
            
            # 增强对比度
            enhancer = ImageEnhance.Contrast(denoised)
            enhanced = enhancer.enhance(2.0)
            
            # 锐化图像
            sharpened = enhanced.filter(ImageFilter.SHARPEN)
            
            return sharpened
        except Exception as e:
            logger.warning(f"图像预处理失败: {str(e)}，将使用原始图像")
            return image
    
    def process_image(self, image_path: str, task_id: str) -> str:
        """
        处理单张图片
        
        参数:
            image_path: 图片路径
            task_id: 任务ID
            
        返回:
            OCR识别出的文本
        """
        try:
            # 检查任务是否已取消
            if self._is_task_cancelled(task_id):
                logger.info(f"任务已取消，停止处理图片: {task_id}")
                raise TaskCancelledException(f"任务已取消: {task_id}")
            
            logger.info(f"开始处理图片: {image_path}")
            
            # 打开图片
            image = Image.open(image_path)
            
            # 预处理图片
            processed_image = self.preprocess_image(image)
            
            # 使用PyTesseract进行OCR识别
            text = pytesseract.image_to_string(
                processed_image,
                lang=self.languages,
                config='--psm 3'  # 页面分割模式3 - 完全自动页面分割，但没有OSD（自动方向和脚本检测）
            )
            
            logger.info(f"图片处理完成，文本长度: {len(text)}")
            
            return text
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"图片OCR处理失败: {str(e)}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
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
        # 为当前任务创建唯一的临时目录
        task_temp_dir = os.path.join(self.temp_image_dir, task_id)
        os.makedirs(task_temp_dir, exist_ok=True)
        
        # 使用共享PDF处理器切分PDF文件
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

    def process_pdf_images(self, image_paths: List[str], task_id: str) -> str:
        """
        处理PDF转换后的图片
        
        参数:
            image_paths: 图片路径列表
            task_id: 任务ID
            
        返回:
            合并后的文本内容
        """
        # 使用共享PDF处理器处理切分后的图片
        return PDFProcessor.process_pdf_images(
            image_paths=image_paths,
            task_id=task_id,
            processor_func=self.process_image,
            cancel_check_func=self._is_task_cancelled
        )

    def process_pdf(self, pdf_path: str, task_id: str) -> str:
        """
        处理PDF文件
        
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
            
            logger.info(f"开始处理PDF: {pdf_path}")
            
            # 第一步：切分PDF为图片
            image_paths = self.split_pdf_to_images(pdf_path, task_id)
            logger.info(f"PDF切分完成，共{len(image_paths)}页")
            
            # 第二步：处理图片进行OCR识别
            result = self.process_pdf_images(image_paths, task_id)
            logger.info(f"PDF OCR处理完成，结果长度: {len(result)}")
            
            # 清理任务临时目录
            task_temp_dir = os.path.join(self.temp_image_dir, task_id)
            try:
                for image_path in image_paths:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                
                if os.path.exists(task_temp_dir):
                    os.rmdir(task_temp_dir)
                    logger.info(f"已清理任务临时目录: {task_temp_dir}")
            except Exception as e:
                logger.warning(f"清理任务临时目录失败: {str(e)}")
            
            return result
            
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.error(f"PDF处理失败: {str(e)}")
            logger.error(f"错误类型: {type(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
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
                
        except Exception as e:
            logger.error(f"文件处理失败: {str(e)}")
            raise
        finally:
            # 无论处理成功还是失败，都标记任务完成
            self.finish_task(task_id)

# 创建单例实例
ocr_service = OCRService() 