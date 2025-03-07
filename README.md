# Py OCR 服务

一个基于 Flask、Tesseract 和 Minio 的 OCR 服务，提供 API 接口供外部调用，将 PDF 文件、图片等转换为文本并存储到 Minio，用户可以通过 API 获取处理状态和结果 URL。

## 功能特点

1. **文件处理**

   - 支持 PDF 和常见图片格式 (PNG, JPG, JPEG, TIFF)
   - 自动文件类型检测和验证
   - 文件大小限制和安全性检查

2. **OCR 能力**

   - 支持中文和英文识别
   - 自动图像预处理优化
   - 高精度文本提取

3. **存储管理**

   - Minio 对象存储集成
   - 自动文件命名和分类
   - 临时文件自动清理

4. **任务管理**
   - 异步任务处理
   - 任务状态实时查询
   - 失败任务自动重试

## 技术栈

- **后端框架:** Flask
- **OCR 引擎:** Tesseract (需安装中文语言包 tesseract-ocr-chi_sim)
- **对象存储:** Minio
- **异步任务队列:** Celery + Redis
- **数据存储:** SQLite
- **日志系统:** Python logging
- **测试框架:** unittest

## 安装与部署

### 环境要求

- Python 3.8+
- Tesseract OCR 引擎
- Redis 服务
- Minio 服务
- 足够的磁盘空间用于临时文件存储

### 安装步骤

1. **安装系统依赖**

#### Windows

```bash
# 下载并安装 Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# 确保安装中文语言包
# 将 Tesseract 安装路径添加到环境变量 PATH 中
```

#### Linux

```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-chi-sim  # 中文简体语言包
```

#### macOS

```bash
brew install tesseract
brew install tesseract-lang  # 安装语言包
```

2. **安装 Python 依赖**

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

3. **配置环境变量**

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，设置必要的配置
```

### 配置说明

主要配置项说明：

```ini
# MinIO配置
MINIO_ENDPOINT=localhost:9000      # MinIO服务地址
MINIO_ACCESS_KEY=minioadmin       # 访问密钥
MINIO_SECRET_KEY=minioadmin       # 密钥
MINIO_SECURE=False               # 是否使用HTTPS
MINIO_BUCKET_NAME=ocr-results    # 存储桶名称

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/0    # Redis连接URL
CELERY_RESULT_BACKEND=redis://localhost:6379/0 # 结果后端URL

# 应用配置
MAX_CONTENT_LENGTH=10485760      # 最大文件大小(10MB)
UPLOAD_FOLDER=temp              # 临时文件目录
```

## 运行服务

### 1. 启动 Redis 服务

```bash
# Windows
redis-server

# Linux/macOS
sudo service redis-server start
```

### 2. 启动 Minio 服务

```bash
# 创建存储桶
mc mb minio/ocr-results

# 启动服务
minio server /data
```

### 3. 启动 Flask 应用

```bash
python app.py
```

### 4. 启动 Celery Worker

```bash
# Windows
celery -A celery_worker.celery worker --pool=solo -l info

# Linux/macOS
celery -A celery_worker.celery worker -l info
```

## API 使用说明

详细的 API 文档请参考 [API.md](API.md)

### 快速开始

1. **上传文件**

```bash
curl -X POST -F "file=@test.pdf" http://localhost:5000/api/upload
```

2. **查询状态**

```bash
curl http://localhost:5000/api/status/<task_id>
```

## 开发指南

### 项目结构

```
py-ocr/
├── app/                    # 应用主目录
│   ├── api/               # API接口
│   ├── config/            # 配置文件
│   ├── models/            # 数据模型
│   ├── services/          # 业务逻辑
│   ├── tasks/             # Celery任务
│   └── utils/             # 工具函数
├── tests/                 # 测试目录
├── .env                   # 环境变量
├── .env.example          # 环境变量示例
├── app.py                # 应用入口
├── celery_worker.py      # Celery工作进程
└── requirements.txt      # 项目依赖
```

### 开发流程

1. **克隆项目**

```bash
git clone <repository_url>
cd py-ocr
```

2. **创建分支**

```bash
git checkout -b feature/your-feature-name
```

3. **提交更改**

```bash
git add .
git commit -m "描述你的更改"
```

4. **运行测试**

```bash
python -m unittest discover -s tests
```

5. **提交 PR**

- 确保所有测试通过
- 更新相关文档
- 提交 Pull Request

## 常见问题

1. **OCR 识别效果不理想**

   - 检查图片质量
   - 确保安装了正确的语言包
   - 尝试调整图像预处理参数

2. **任务处理失败**

   - 检查 Redis 服务状态
   - 查看 Celery worker 日志
   - 验证文件格式和大小

3. **存储问题**
   - 确认 Minio 服务状态
   - 检查存储桶权限
   - 验证磁盘空间

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或联系项目维护者。
