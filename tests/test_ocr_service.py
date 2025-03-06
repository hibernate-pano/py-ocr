import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock

from app.services.ocr_service import OCRService

class TestOCRService(unittest.TestCase):
    """OCR服务测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.ocr_service = OCRService()
        
        # 创建临时目录
        self.temp_dir = tempfile.TemporaryDirectory()
    
    def tearDown(self):
        """测试后清理"""
        self.temp_dir.cleanup()
    
    @patch('app.services.ocr_service.pytesseract')
    def test_process_image(self, mock_pytesseract):
        """测试图片处理"""
        # 设置模拟返回值
        mock_pytesseract.image_to_string.return_value = "测试文本"
        
        # 创建测试图片文件
        test_image_path = os.path.join(self.temp_dir.name, 'test.png')
        with open(test_image_path, 'w') as f:
            f.write('')  # 创建空文件
        
        # 模拟PIL.Image
        with patch('app.services.ocr_service.Image') as mock_image:
            mock_image.open.return_value = MagicMock()
            
            # 调用被测试方法
            result = self.ocr_service.process_image(test_image_path)
            
            # 验证结果
            self.assertEqual(result, "测试文本")
            mock_pytesseract.image_to_string.assert_called_once()
    
    @patch('app.services.ocr_service.pdf2image')
    @patch('app.services.ocr_service.pytesseract')
    def test_process_pdf(self, mock_pytesseract, mock_pdf2image):
        """测试PDF处理"""
        # 设置模拟返回值
        mock_pytesseract.image_to_string.return_value = "测试文本"
        mock_pdf2image.convert_from_path.return_value = [MagicMock(), MagicMock()]  # 模拟两页PDF
        
        # 创建测试PDF文件
        test_pdf_path = os.path.join(self.temp_dir.name, 'test.pdf')
        with open(test_pdf_path, 'w') as f:
            f.write('')  # 创建空文件
        
        # 调用被测试方法
        result = self.ocr_service.process_pdf(test_pdf_path)
        
        # 验证结果
        self.assertEqual(result, "测试文本\n\n测试文本")
        self.assertEqual(mock_pytesseract.image_to_string.call_count, 2)  # 应该被调用两次（每页一次）
        mock_pdf2image.convert_from_path.assert_called_once()

if __name__ == '__main__':
    unittest.main() 