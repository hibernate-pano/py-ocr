import os
import logging
import pytesseract
from PIL import Image
import pdf2image
import tempfile

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
    
    def process_image(self, image_path):
        """处理图片文件识别文本"""
        try:
            logger.info(f"开始处理图片: {image_path}")
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=self.languages)
            logger.info(f"图片OCR处理完成: {image_path}")
            return text
        except Exception as e:
            logger.error(f"图片OCR处理失败: {str(e)}")
            raise
    
    def process_pdf(self, pdf_path):
        """处理PDF文件识别文本"""
        try:
            logger.info(f"开始处理PDF: {pdf_path}")
            
            # 将PDF转换为图片
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info(f"将PDF转换为图片: {pdf_path}")
                images = pdf2image.convert_from_path(pdf_path, output_folder=temp_dir)
                
                all_text = []
                # 对每一页进行OCR处理
                for i, image in enumerate(images):
                    logger.info(f"处理PDF第{i+1}页")
                    text = pytesseract.image_to_string(image, lang=self.languages)
                    all_text.append(text)
                
                logger.info(f"PDF OCR处理完成: {pdf_path}")
                return "\n\n".join(all_text)
        except Exception as e:
            logger.error(f"PDF OCR处理失败: {str(e)}")
            raise
    
    def process_file(self, file_path):
        """
        处理文件，自动判断类型并进行OCR处理
        
        参数:
            file_path: 文件路径
            
        返回:
            识别出的文本内容
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # 根据文件类型进行处理
        if ext == '.pdf':
            return self.process_pdf(file_path)
        elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
            return self.process_image(file_path)
        else:
            error_msg = f"不支持的文件类型: {ext}"
            logger.error(error_msg)
            raise ValueError(error_msg)

# 创建单例实例
ocr_service = OCRService() 