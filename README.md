# Py OCR 服务

一个基于 Flask、Tesseract 和 Minio 的 OCR 服务，提供 API 接口供外部调用，将 PDF 文件、图片等转换为文本并存储到 Minio，用户可以通过 API 获取处理状态和结果 URL。

## 技术栈

- **后端框架:** Flask
- **OCR 引擎:** Tesseract (需安装中文语言包 tesseract-ocr-chi_sim)
- **对象存储:** Minio
- **异步任务队列:** Celery + Redis
- **数据存储:** SQLite

## 功能

1. **文件上传:** 支持上传 PDF 和常见图片格式(PNG, JPG, JPEG, TIFF)
2. **异步处理:** 使用 Celery 任务队列异步处理 OCR 任务
3. **状态查询:** 查询 OCR 处理任务的状态
4. **结果获取:** 获取 OCR 处理结果的 Minio URL

## 安装与部署

### 环境准备

1. 安装 Python 3.8+
2. 安装 Tesseract OCR 引擎
3. 安装中文语言包 (tesseract-ocr-chi_sim)
4. 安装并运行 Redis 服务
5. 安装并运行 Minio 服务

#### Windows 安装 Tesseract

```
# 下载并安装Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# 确保安装中文语言包
# 将Tesseract安装路径添加到环境变量PATH中
```

#### Linux 安装 Tesseract

```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-chi-sim  # 中文简体语言包
```

### 安装项目依赖

```bash
pip install -r requirements.txt
```

### 配置

1. 复制 `.env.example` 文件为 `.env`
2. 根据实际环境修改 `.env` 文件中的配置

```
# MinIO配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=False
MINIO_BUCKET_NAME=ocr-results

# Celery配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 应用配置
MAX_CONTENT_LENGTH=10485760
UPLOAD_FOLDER=temp
```

## 运行

### 启动 Flask 应用

```bash
python app.py
```

### 启动 Celery Worker

```bash
# Windows
celery -A celery_worker.celery worker --pool=solo -l info

# Linux/macOS
celery -A celery_worker.celery worker -l info
```

## API 文档

### 1. 上传文件

- **URL:** `/api/upload`
- **方法:** `POST`
- **内容类型:** `multipart/form-data`
- **参数:** `file` (文件)
- **响应:**
  - 成功: `{"task_id": "uuid"}`
  - 失败: `{"error": "错误信息"}`

### 2. 查询任务状态

- **URL:** `/api/status/<task_id>`
- **方法:** `GET`
- **响应:**
  - 处理中: `{"status": "processing"}`
  - 已完成: `{"status": "completed", "minio_url": "文件URL"}`
  - 失败: `{"status": "failed", "error": "错误信息"}`
  - 任务 ID 不存在: `{"error": "Task ID not found"}`

## 测试

运行单元测试:

```bash
python -m unittest discover -s tests
```

## 项目结构

```
py-ocr/
├── app/
│   ├── api/             # API接口
│   ├── config/          # 配置文件
│   ├── models/          # 数据模型
│   ├── services/        # 业务逻辑
│   ├── tasks/           # Celery任务
│   └── utils/           # 工具函数
├── tests/               # 测试目录
├── .env                 # 环境变量
├── .env.example         # 环境变量示例
├── app.py               # 应用入口
├── celery_worker.py     # Celery工作进程
└── requirements.txt     # 项目依赖
```

## 许可证

MIT
