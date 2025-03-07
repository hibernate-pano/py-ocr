# Py OCR 服务

一个基于 Flask、Tesseract 和 Minio 的 OCR 服务，提供 API 接口供外部调用，将 PDF 文件、图片等转换为文本并存储到 Minio，用户可以通过 API 获取处理状态和结果 URL。同时，集成多模态大模型能力，提供更高精度的图像文本识别服务。

## 功能特点

1. **文件处理**

   - 支持 PDF 和常见图片格式 (PNG, JPG, JPEG, TIFF)
   - 自动文件类型检测和验证
   - 文件大小限制和安全性检查

2. **OCR 能力**

   - 支持中文和英文识别
   - 自动图像预处理优化
   - 高精度文本提取

3. **多模态大模型能力**

   - 通过硅基流动 API 调用多模态大模型
   - 更高精度的图像文本识别
   - 复杂图像内容理解和提取
   - 强大的重试机制和错误恢复能力

4. **Ollama OCR 能力**

   - 集成 [Ollama-OCR](https://github.com/imanoop7/Ollama-OCR) 项目提供高精度识别
   - 支持多种多模态模型：LLaVA 7B, Llama 3.2 Vision 等
   - 支持多种输出格式：纯文本、Markdown、JSON、结构化数据、键值对
   - 本地部署，保护数据隐私和安全

5. **存储管理**

   - Minio 对象存储集成
   - 自动文件命名和分类
   - 临时文件自动清理

6. **任务管理**
   - 异步任务处理
   - 任务状态实时查询
   - 失败任务自动重试

## 技术栈

- **后端框架:** Flask
- **OCR 引擎:** Tesseract (需安装中文语言包 tesseract-ocr-chi_sim)
- **多模态大模型:**
  - 通过硅基流动 API 调用
  - 基于 Ollama 的本地模型
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
- 硅基流动 API 账号和密钥（用于多模态大模型功能）
- Ollama (用于本地部署多模态模型，可选)

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

#### 安装 Ollama (可选)

1. **安装 Ollama**
   按照 [Ollama 官方文档](https://github.com/ollama/ollama) 的指引安装 Ollama

2. **下载所需模型**

   ```bash
   # 下载 LLaVA 模型用于图像识别
   ollama pull llava

   # 或者下载 Llama 3.2 Vision 模型（推荐）
   ollama pull llama3.2-vision:11b
   ```

3. **安装 ollama-ocr 包**
   ```bash
   pip install ollama-ocr
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

# 硅基流动API配置
SILICON_FLOW_API_KEY=your_api_key       # 硅基流动API密钥
SILICON_FLOW_API_URL=https://api.siliconflow.com/v1  # API地址

# Ollama配置
OLLAMA_BASE_URL=http://localhost:11434   # Ollama API地址
OLLAMA_MODEL=llama3.2-vision:11b        # 使用的模型名称
OLLAMA_OUTPUT_FORMAT=plain_text         # 输出格式（plain_text/markdown/json/structured/key_value）
OLLAMA_TIMEOUT=120                      # API超时时间（秒）
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

1. **OCR 服务 - 上传文件**

```bash
curl -X POST -F "file=@test.pdf" http://localhost:5000/api/upload
```

2. **OCR 服务 - 查询状态**

```bash
curl http://localhost:5000/api/status/<task_id>
```

3. **LLM 服务 - 上传文件**

```bash
curl -X POST -F "file=@test.pdf" http://localhost:5000/api/llm/upload
```

4. **LLM 服务 - 查询状态**

```bash
curl http://localhost:5000/api/llm/status/<task_id>
```

5. **Ollama OCR 服务 - 上传文件**

```bash
curl -X POST -F "file=@test.pdf" http://localhost:5000/api/ocr/upload
```

6. **Ollama OCR 服务 - 查询状态**

```bash
curl http://localhost:5000/api/ocr/status/<task_id>
```

## OCR 引擎对比

现在本服务提供三种 OCR 引擎选择：

| 功能         | Tesseract OCR | 多模态大模型 (硅基流动) | Ollama-OCR (GitHub 项目) |
| ------------ | ------------- | ----------------------- | ------------------------ |
| 处理速度     | 快            | 较慢                    | 中等                     |
| 识别精度     | 中等          | 高                      | 高                       |
| 复杂布局处理 | 有限          | 优秀                    | 较好                     |
| 图表理解     | 不支持        | 支持                    | 支持                     |
| 手写文字识别 | 有限          | 优秀                    | 较好                     |
| 低质量图像   | 效果一般      | 较好                    | 较好                     |
| API 费用     | 无            | 基于使用量              | 无                       |
| 离线使用     | 支持          | 不支持                  | 支持                     |
| 硬件要求     | 低            | 低                      | 高 (建议使用 GPU)        |
| 多语言支持   | 需安装语言包  | 内置多语言支持          | 内置多语言支持           |
| 输出格式     | 纯文本        | 纯文本                  | 多种格式                 |

根据您的具体需求和环境条件，选择合适的 OCR 引擎：

1. **Tesseract OCR**: 适合简单文档、本地处理、低资源环境
2. **多模态大模型**: 适合复杂文档、高质量要求、无本地 GPU
3. **Ollama-OCR**: 适合复杂文档、本地部署、多格式输出需求

## 开发指南

### 项目结构

```
py-ocr/
├── app/                    # 应用主目录
│   ├── api/               # API接口
│   ├── config/            # 配置文件
│   ├── models/            # 数据模型
│   ├── services/          # 业务逻辑
│   │   ├── minio_service.py  # MinIO服务
│   │   ├── ocr_service.py    # OCR服务
│   │   └── llm_service.py    # LLM服务
│   ├── tasks/             # Celery任务
│   │   ├── ocr_task.py       # OCR任务
│   │   └── llm_task.py       # LLM任务
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

## LLM 服务增强功能

### 智能重试机制

LLM 服务现在具有增强的错误处理和重试能力：

1. **自适应重试策略**

   - 基于错误类型动态调整重试延迟
   - 针对请求限制（429）错误使用更长的重试等待时间
   - 服务器错误（5xx）自动重试多达 5 次

2. **详细请求跟踪**

   - 每个请求都有唯一的请求 ID 用于跟踪和调试
   - 详细的日志记录请求处理的各个阶段
   - 记录 API 调用耗时和响应状态

3. **PDF 分页处理优化**

   - 每页 PDF 单独处理并带有独立的重试机制
   - 即使部分页面失败，仍能继续处理其他页面
   - 最终结果包含处理统计摘要

4. **错误恢复**
   - 连接超时和网络错误自动恢复
   - API 限流和服务暂时不可用时智能等待
   - 不同类型错误的个性化处理

这些增强功能使 LLM 服务在网络不稳定或 API 服务波动的情况下仍能稳定运行。

## 常见问题

1. **OCR 识别效果不理想**

   - 检查图片质量
   - 确保安装了正确的语言包
   - 尝试调整图像预处理参数
   - 考虑使用 LLM 识别路径

2. **LLM 服务响应缓慢**

   - 检查网络连接
   - 验证 API 密钥是否有效
   - 确认硅基流动服务状态
   - 检查文件大小是否过大

3. **任务处理失败**

   - 检查 Redis 服务状态
   - 查看 Celery worker 日志
   - 验证文件格式和大小

4. **存储问题**
   - 确认 Minio 服务状态
   - 检查存储桶权限
   - 验证磁盘空间

## LLM 和 OCR 功能对比

| 功能         | OCR（Tesseract） | LLM（多模态大模型） |
| ------------ | ---------------- | ------------------- |
| 处理速度     | 较快             | 较慢                |
| 识别精度     | 中等             | 高                  |
| 复杂布局处理 | 有限             | 优秀                |
| 图表理解     | 不支持           | 支持                |
| 手写文字识别 | 有限             | 优秀                |
| 低质量图像   | 效果一般         | 较好                |
| API 费用     | 无               | 基于使用量          |
| 离线使用     | 支持             | 不支持              |
| 错误恢复能力 | 基础             | 高级                |

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
