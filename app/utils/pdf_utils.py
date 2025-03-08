import os
import logging
from typing import List, Union, Callable, Optional
import pdf2image
from PIL import Image

logger = logging.getLogger(__name__)

class PDFProcessor:
    """
    PDF处理工具类，提供通用的PDF转图片功能
    """
    
    @staticmethod
    def split_pdf_to_images(
        pdf_path: str, 
        output_dir: str, 
        task_id: str,
        dpi: int = 300,
        fmt: str = 'png',
        cancel_check_func: Optional[Callable[[str], bool]] = None,
        return_paths: bool = True,
        thread_count: int = 2,
        use_pdftocairo: bool = True
    ) -> Union[List[str], List[Image.Image]]:
        """
        将PDF文件切分为图片
        
        参数:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            task_id: 任务ID
            dpi: 图片分辨率DPI
            fmt: 输出图片格式
            cancel_check_func: 任务取消检查函数
            return_paths: 是否返回图片路径（False则返回图片对象）
            thread_count: 处理线程数
            use_pdftocairo: 是否使用pdftocairo后端
            
        返回:
            图片文件路径列表或图片对象列表
        """
        logger.info(f"开始切分PDF: {pdf_path}, 任务ID: {task_id}")
        
        # 检查PDF文件是否存在
        if not os.path.exists(pdf_path):
            error_msg = f"PDF文件不存在: {pdf_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 检查输出目录是否存在，不存在则创建
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"创建输出目录: {output_dir}")
        
        # 检查任务是否取消
        if cancel_check_func and cancel_check_func(task_id):
            cancel_msg = f"任务已取消，停止切分PDF: {task_id}"
            logger.info(cancel_msg)
            raise TaskCancelledException(cancel_msg)
        
        try:
            # 读取PDF文件内容
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()
                
            # 检查PDF文件大小
            pdf_size_mb = len(pdf_content) / (1024 * 1024)
            logger.info(f"PDF文件大小: {pdf_size_mb:.2f} MB")
            
            # 大文件警告
            if pdf_size_mb > 20:
                logger.warning(f"PDF文件较大 ({pdf_size_mb:.2f} MB)，处理可能需要较长时间")
            
            # 设置参数
            convert_args = {
                'dpi': dpi,
                'fmt': fmt,
            }
            
            # 根据是否返回路径设置参数
            if return_paths:
                convert_args.update({
                    'output_folder': output_dir,
                    'paths_only': True,
                    'thread_count': thread_count,
                    'use_pdftocairo': use_pdftocairo
                })
            
            # 转换PDF为图片
            logger.info(f"开始转换PDF为图片，参数: DPI={dpi}, 格式={fmt}")
            images = pdf2image.convert_from_bytes(pdf_content, **convert_args)
            
            # 如果需要返回路径但convert_from_bytes不支持paths_only参数的情况
            if return_paths and not isinstance(images[0], str):
                image_paths = []
                for i, image in enumerate(images):
                    # 检查任务是否取消
                    if cancel_check_func and cancel_check_func(task_id):
                        cancel_msg = f"任务已取消，停止保存PDF图片: {task_id}"
                        logger.info(cancel_msg)
                        raise TaskCancelledException(cancel_msg)
                    
                    # 保存图片
                    image_path = os.path.join(output_dir, f"page_{i+1}.{fmt}")
                    image.save(image_path, fmt.upper())
                    image_paths.append(image_path)
                    logger.debug(f"保存PDF第{i+1}页为图片: {image_path}")
                
                images = image_paths
            
            logger.info(f"PDF切分完成，共生成{len(images)}张图片")
            return images
            
        except Exception as e:
            logger.error(f"PDF切分失败: {str(e)}")
            raise
            
    @staticmethod
    def process_pdf_images(
        image_paths: List[str],
        task_id: str,
        processor_func: Callable[[str, str], str],
        cancel_check_func: Optional[Callable[[str], bool]] = None
    ) -> str:
        """
        处理PDF切分后的图片
        
        参数:
            image_paths: 图片路径列表
            task_id: 任务ID
            processor_func: 图片处理函数，接受图片路径和任务ID，返回处理结果
            cancel_check_func: 任务取消检查函数
            
        返回:
            处理结果文本
        """
        logger.info(f"开始处理PDF图片，共{len(image_paths)}张，任务ID: {task_id}")
        
        all_text = []
        failed_pages = []
        
        for i, image_path in enumerate(image_paths):
            # 检查任务是否取消
            if cancel_check_func and cancel_check_func(task_id):
                cancel_msg = f"任务已取消，停止处理PDF图片: {task_id}"
                logger.info(cancel_msg)
                raise TaskCancelledException(cancel_msg)
            
            try:
                logger.info(f"处理PDF第{i+1}页图片: {image_path}")
                page_text = processor_func(image_path, task_id)
                all_text.append(f"--- 第{i+1}页 ---\n{page_text}")
                logger.info(f"PDF第{i+1}页处理完成，文本长度: {len(page_text)}")
            except Exception as e:
                logger.error(f"处理PDF第{i+1}页失败: {str(e)}")
                failed_pages.append(i+1)
                all_text.append(f"--- 第{i+1}页（处理失败）---")
        
        # 合并所有页面的文本
        combined_text = "\n\n".join(all_text)
        
        # 添加处理摘要
        if failed_pages:
            footer = f"\n\n--- 处理摘要 ---\n总页数: {len(image_paths)}\n成功页数: {len(image_paths) - len(failed_pages)}\n失败页数: {len(failed_pages)}\n失败页码: {', '.join(map(str, failed_pages))}"
        else:
            footer = f"\n\n--- 处理摘要 ---\n总页数: {len(image_paths)}\n所有页面处理成功"
            
        combined_text += footer
        
        logger.info(f"PDF图片处理完成，总共{len(image_paths)}页，失败{len(failed_pages)}页")
        return combined_text


class TaskCancelledException(Exception):
    """任务取消异常"""
    
    def __init__(self, message):
        self.message = message
        super().__init__(self.message) 