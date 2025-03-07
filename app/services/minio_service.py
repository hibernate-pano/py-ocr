import logging
from minio import Minio
from minio.error import S3Error
from flask import current_app
import os

logger = logging.getLogger(__name__)

class MinioService:
    """MinIO服务类，提供对象存储相关操作"""
    
    def __init__(self):
        self.client = None
        self.bucket_name = None
        self._endpoint = None
        self._access_key = None
        self._secret_key = None
        self._secure = None
    
    def _load_config(self):
        """从环境变量或应用配置加载MinIO配置"""
        try:
            # 优先从环境变量获取配置
            self._endpoint = os.getenv('MINIO_ENDPOINT') or current_app.config['MINIO_ENDPOINT']
            self._access_key = os.getenv('MINIO_ACCESS_KEY') or current_app.config['MINIO_ACCESS_KEY']
            self._secret_key = os.getenv('MINIO_SECRET_KEY') or current_app.config['MINIO_SECRET_KEY']
            self._secure = os.getenv('MINIO_SECURE', '').lower() == 'true' if os.getenv('MINIO_SECURE') else current_app.config['MINIO_SECURE']
            self.bucket_name = os.getenv('MINIO_BUCKET_NAME') or current_app.config['MINIO_BUCKET_NAME']
            
            logger.info("MinIO配置加载成功")
        except Exception as e:
            logger.error(f"MinIO配置加载失败: {str(e)}")
            raise
    
    def connect(self):
        """连接到MinIO服务器"""
        if self.client is not None:
            return
        
        try:
            # 加载配置
            self._load_config()
            
            # 创建MinIO客户端
            self.client = Minio(
                endpoint=self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure
            )
            
            # 确保bucket存在
            self.ensure_bucket_exists()
            
            logger.info(f"成功连接到MinIO服务器: {self._endpoint}")
        except Exception as e:
            logger.error(f"MinIO连接失败: {str(e)}")
            raise
    
    def ensure_bucket_exists(self):
        """确保存储桶存在，如不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                # 设置桶策略为公开读取
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                        }
                    ]
                }
                self.client.set_bucket_policy(self.bucket_name, policy)
                logger.info(f"已创建存储桶: {self.bucket_name}")
        except Exception as e:
            logger.error(f"确保存储桶存在失败: {str(e)}")
            raise
    
    def upload_text(self, object_name, text_content):
        """上传文本内容到MinIO"""
        try:
            self.connect()
            
            # 确保text_content是字符串类型
            if isinstance(text_content, bytes):
                text_content = text_content.decode('utf-8')
            elif not isinstance(text_content, str):
                text_content = str(text_content)
            
            # 将文本转换为字节流
            text_bytes = text_content.encode('utf-8')
            
            # 上传到MinIO
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=text_bytes,
                length=len(text_bytes),
                content_type='text/plain'
            )
            
            # 生成文件访问URL（7天有效）
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=7*24*60*60  # 7天有效期
            )
            
            logger.info(f"已上传文本到: {object_name}")
            return url
        except S3Error as e:
            logger.error(f"MinIO上传失败: {str(e)}")
            raise
    
    def upload_file(self, object_name, file_path):
        """上传文件到MinIO"""
        try:
            self.connect()
            
            # 上传到MinIO
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path
            )
            
            # 生成文件访问URL（7天有效）
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=7*24*60*60  # 7天有效期
            )
            
            logger.info(f"已上传文件到: {object_name}")
            return url
        except S3Error as e:
            logger.error(f"MinIO上传失败: {str(e)}")
            raise

# 创建单例实例
minio_service = MinioService() 