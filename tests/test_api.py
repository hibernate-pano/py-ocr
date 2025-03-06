import unittest
import json
import io
import os
from unittest.mock import patch, MagicMock

from app import create_app
from app.models.task import TaskStatus

class TestAPI(unittest.TestCase):
    """API接口测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # 确保临时上传目录存在
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    @patch('app.api.routes.process_ocr')
    @patch('app.api.routes.save_task_status')
    def test_upload_file(self, mock_save_task_status, mock_process_ocr):
        """测试文件上传接口"""
        # 模拟文件
        data = {'file': (io.BytesIO(b'test file content'), 'test.pdf')}
        
        # 发送请求
        response = self.client.post('/api/upload', 
                                    data=data, 
                                    content_type='multipart/form-data')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('task_id', response_data)
        
        # 验证任务状态保存和任务队列
        mock_save_task_status.assert_called_once()
        mock_process_ocr.delay.assert_called_once()
    
    @patch('app.api.routes.get_task_status')
    def test_get_status_processing(self, mock_get_task_status):
        """测试获取处理中的任务状态"""
        # 模拟返回处理中的任务
        mock_get_task_status.return_value = {
            'id': 'test-task-id',
            'status': TaskStatus.PROCESSING.value,
            'result_url': None,
            'error': None
        }
        
        # 发送请求
        response = self.client.get('/api/status/test-task-id')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], TaskStatus.PROCESSING.value)
    
    @patch('app.api.routes.get_task_status')
    def test_get_status_completed(self, mock_get_task_status):
        """测试获取已完成的任务状态"""
        # 模拟返回已完成的任务
        mock_get_task_status.return_value = {
            'id': 'test-task-id',
            'status': TaskStatus.COMPLETED.value,
            'result_url': 'http://minio.example.com/bucket/test-task-id.txt',
            'error': None
        }
        
        # 发送请求
        response = self.client.get('/api/status/test-task-id')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], TaskStatus.COMPLETED.value)
        self.assertEqual(response_data['minio_url'], 'http://minio.example.com/bucket/test-task-id.txt')
    
    @patch('app.api.routes.get_task_status')
    def test_get_status_failed(self, mock_get_task_status):
        """测试获取失败的任务状态"""
        # 模拟返回失败的任务
        mock_get_task_status.return_value = {
            'id': 'test-task-id',
            'status': TaskStatus.FAILED.value,
            'result_url': None,
            'error': 'OCR处理失败'
        }
        
        # 发送请求
        response = self.client.get('/api/status/test-task-id')
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], TaskStatus.FAILED.value)
        self.assertEqual(response_data['error'], 'OCR处理失败')
    
    @patch('app.api.routes.get_task_status')
    def test_get_status_not_found(self, mock_get_task_status):
        """测试获取不存在的任务状态"""
        # 模拟任务不存在
        mock_get_task_status.return_value = None
        
        # 发送请求
        response = self.client.get('/api/status/non-existent-task-id')
        
        # 验证响应
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)

if __name__ == '__main__':
    unittest.main() 