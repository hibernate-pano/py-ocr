# Py OCR 服务 API 文档

## 基本信息

- **基础 URL**: `http://localhost:5000/api`
- **内容类型**: 请求和响应均使用 JSON 格式，除非特别说明
- **版本**: v1.0.0

## 认证

目前 API 不需要认证。未来版本将支持以下认证方式：

- API Key 认证
- OAuth2 认证
- JWT 认证

## 接口列表

### 1. OCR 文件上传接口

用于上传需要 OCR 处理的文件。

- **URL**: `/upload`
- **方法**: `POST`
- **内容类型**: `multipart/form-data`
- **参数**:

  | 参数名 | 类型 | 必填 | 描述                                    |
  | ------ | ---- | ---- | --------------------------------------- |
  | file   | 文件 | 是   | 需要上传的文件，支持 PDF 和常见图片格式 |

- **响应**:

  - **成功** (HTTP 200):
    ```json
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "message": "文件上传成功，正在处理中"
    }
    ```
  - **失败** (HTTP 400):
    ```json
    {
      "error": "没有上传文件",
      "code": "NO_FILE_UPLOADED"
    }
    ```
    或
    ```json
    {
      "error": "不支持的文件类型",
      "code": "UNSUPPORTED_FILE_TYPE",
      "supported_types": ["pdf", "png", "jpg", "jpeg", "tiff"]
    }
    ```
    或
    ```json
    {
      "error": "文件大小超过限制",
      "code": "FILE_TOO_LARGE",
      "max_size": 10485760
    }
    ```
  - **失败** (HTTP 500):
    ```json
    {
      "error": "服务器内部错误",
      "code": "INTERNAL_SERVER_ERROR"
    }
    ```

- **示例**:
  ```bash
  curl -X POST -F "file=@test.pdf" http://localhost:5000/api/upload
  ```

### 2. LLM 文件上传接口

用于上传需要通过多模态大模型处理的文件。

- **URL**: `/llm/upload`
- **方法**: `POST`
- **内容类型**: `multipart/form-data`
- **参数**:

  | 参数名 | 类型 | 必填 | 描述                                    |
  | ------ | ---- | ---- | --------------------------------------- |
  | file   | 文件 | 是   | 需要上传的文件，支持 PDF 和常见图片格式 |

- **响应**:

  - **成功** (HTTP 200):
    ```json
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "message": "文件上传成功，开始LLM处理"
    }
    ```
  - **失败** (HTTP 400):
    ```json
    {
      "error": "没有上传文件",
      "code": "NO_FILE_UPLOADED"
    }
    ```
    或
    ```json
    {
      "error": "不支持的文件类型",
      "code": "UNSUPPORTED_FILE_TYPE",
      "supported_types": ["pdf", "png", "jpg", "jpeg", "tiff"]
    }
    ```
    或
    ```json
    {
      "error": "文件大小超过限制",
      "code": "FILE_TOO_LARGE",
      "max_size": 10485760
    }
    ```
  - **失败** (HTTP 500):
    ```json
    {
      "error": "服务器内部错误",
      "code": "INTERNAL_SERVER_ERROR"
    }
    ```

- **示例**:
  ```bash
  curl -X POST -F "file=@test.pdf" http://localhost:5000/api/llm/upload
  ```

### 3. OCR 查询任务状态接口

用于获取 OCR 任务的处理状态和结果。

- **URL**: `/status/<task_id>`
- **方法**: `GET`
- **URL 参数**:

  | 参数名  | 类型   | 必填 | 描述    |
  | ------- | ------ | ---- | ------- |
  | task_id | 字符串 | 是   | 任务 ID |

- **响应**:

  - **成功，任务处理中** (HTTP 200):
    ```json
    {
      "status": "processing",
      "progress": 45,
      "started_at": "2024-03-07T10:00:00Z",
      "estimated_completion": "2024-03-07T10:01:00Z"
    }
    ```
  - **成功，任务已完成** (HTTP 200):
    ```json
    {
      "status": "completed",
      "minio_url": "http://minio.example.com/ocr-results/550e8400-e29b-41d4-a716-446655440000.txt",
      "completed_at": "2024-03-07T10:01:00Z",
      "processing_time": 60,
      "file_size": 1024,
      "text_length": 500
    }
    ```
  - **成功，任务失败** (HTTP 200):
    ```json
    {
      "status": "failed",
      "error": "OCR处理失败: 文件损坏",
      "code": "OCR_PROCESSING_ERROR",
      "failed_at": "2024-03-07T10:01:00Z",
      "retry_count": 3
    }
    ```
  - **失败，任务不存在** (HTTP 404):
    ```json
    {
      "error": "Task ID not found",
      "code": "TASK_NOT_FOUND"
    }
    ```

- **示例**:
  ```bash
  curl http://localhost:5000/api/status/550e8400-e29b-41d4-a716-446655440000
  ```

### 4. LLM 查询任务状态接口

用于获取 LLM 任务的处理状态和结果。

- **URL**: `/llm/status/<task_id>`
- **方法**: `GET`
- **URL 参数**:

  | 参数名  | 类型   | 必填 | 描述    |
  | ------- | ------ | ---- | ------- |
  | task_id | 字符串 | 是   | 任务 ID |

- **响应**:
  与 OCR 状态查询接口相同。

- **示例**:
  ```bash
  curl http://localhost:5000/api/llm/status/550e8400-e29b-41d4-a716-446655440000
  ```

### 5. OCR 取消任务接口

用于取消正在进行的 OCR 任务。

- **URL**: `/cancel/<task_id>`
- **方法**: `POST`
- **URL 参数**:

  | 参数名  | 类型   | 必填 | 描述    |
  | ------- | ------ | ---- | ------- |
  | task_id | 字符串 | 是   | 任务 ID |

- **响应**:

  - **成功** (HTTP 200):
    ```json
    {
      "message": "任务已取消"
    }
    ```
  - **失败** (HTTP 400):
    ```json
    {
      "error": "只能取消处理中的任务",
      "current_status": "completed"
    }
    ```
  - **失败，任务不存在** (HTTP 404):
    ```json
    {
      "error": "Task ID not found",
      "code": "TASK_NOT_FOUND"
    }
    ```

- **示例**:
  ```bash
  curl -X POST http://localhost:5000/api/cancel/550e8400-e29b-41d4-a716-446655440000
  ```

### 6. LLM 取消任务接口

用于取消正在进行的 LLM 任务。

- **URL**: `/llm/cancel/<task_id>`
- **方法**: `POST`
- **URL 参数**:

  | 参数名  | 类型   | 必填 | 描述    |
  | ------- | ------ | ---- | ------- |
  | task_id | 字符串 | 是   | 任务 ID |

- **响应**:
  与 OCR 取消任务接口相同。

- **示例**:
  ```bash
  curl -X POST http://localhost:5000/api/llm/cancel/550e8400-e29b-41d4-a716-446655440000
  ```

### 7. 批量查询任务状态接口

用于批量查询多个任务的状态。

- **URL**: `/status/batch`
- **方法**: `POST`
- **内容类型**: `application/json`
- **请求体**:
  ```json
  {
    "task_ids": [
      "550e8400-e29b-41d4-a716-446655440000",
      "550e8400-e29b-41d4-a716-446655440001"
    ]
  }
  ```
- **响应**:
  ```json
  {
    "results": [
      {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "completed",
        "minio_url": "http://minio.example.com/ocr-results/550e8400-e29b-41d4-a716-446655440000.txt"
      },
      {
        "task_id": "550e8400-e29b-41d4-a716-446655440001",
        "status": "processing",
        "progress": 45
      }
    ]
  }
  ```

### 8. Ollama OCR 文件上传接口

用于上传需要通过 Ollama 处理的文件，利用 Ollama 的多模态模型识别图片中的文本。

- **URL**: `/ocr/upload`
- **方法**: `POST`
- **内容类型**: `multipart/form-data`
- **参数**:

  | 参数名 | 类型 | 必填 | 描述                                    |
  | ------ | ---- | ---- | --------------------------------------- |
  | file   | 文件 | 是   | 需要上传的文件，支持 PDF 和常见图片格式 |

- **响应**:

  - **成功** (HTTP 200):
    ```json
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "message": "文件上传成功，正在使用Ollama OCR处理中"
    }
    ```
  - **失败** (HTTP 400):
    ```json
    {
      "error": "没有上传文件",
      "code": "NO_FILE_UPLOADED"
    }
    ```
    或
    ```json
    {
      "error": "不支持的文件类型",
      "code": "UNSUPPORTED_FILE_TYPE",
      "supported_types": ["pdf", "png", "jpg", "jpeg", "tiff"]
    }
    ```
    或
    ```json
    {
      "error": "文件大小超过限制",
      "code": "FILE_TOO_LARGE",
      "max_size": 10485760
    }
    ```
  - **失败** (HTTP 500):
    ```json
    {
      "error": "服务器内部错误",
      "code": "INTERNAL_SERVER_ERROR"
    }
    ```

- **示例**:
  ```bash
  curl -X POST -F "file=@test.pdf" http://localhost:5000/api/ocr/upload
  ```

### 9. Ollama OCR 查询任务状态接口

用于获取 Ollama OCR 任务的处理状态和结果。

- **URL**: `/ocr/status/<task_id>`
- **方法**: `GET`
- **URL 参数**:

  | 参数名  | 类型   | 必填 | 描述    |
  | ------- | ------ | ---- | ------- |
  | task_id | 字符串 | 是   | 任务 ID |

- **响应**:

  - **成功，任务处理中** (HTTP 200):
    ```json
    {
      "status": "processing",
      "task_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```
  - **成功，任务已完成** (HTTP 200):
    ```json
    {
      "status": "completed",
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "minio_url": "http://minio.example.com/ocr-results/550e8400-e29b-41d4-a716-446655440000.txt"
    }
    ```
  - **成功，任务失败** (HTTP 200):
    ```json
    {
      "status": "failed",
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "error": "Ollama OCR处理失败: 服务不可用"
    }
    ```
  - **失败，任务不存在** (HTTP 404):
    ```json
    {
      "error": "Task ID not found",
      "code": "TASK_NOT_FOUND"
    }
    ```

- **示例**:
  ```bash
  curl http://localhost:5000/api/ocr/status/550e8400-e29b-41d4-a716-446655440000
  ```

### 10. Ollama OCR 取消任务接口

用于取消正在进行的 Ollama OCR 任务。

- **URL**: `/ocr/cancel/<task_id>`
- **方法**: `POST`
- **URL 参数**:

  | 参数名  | 类型   | 必填 | 描述    |
  | ------- | ------ | ---- | ------- |
  | task_id | 字符串 | 是   | 任务 ID |

- **响应**:

  - **成功** (HTTP 200):
    ```json
    {
      "message": "任务已取消"
    }
    ```
  - **失败** (HTTP 400):
    ```json
    {
      "error": "只能取消处理中的任务",
      "current_status": "completed"
    }
    ```
    或
    ```json
    {
      "error": "取消任务失败",
      "code": "CANCEL_FAILED"
    }
    ```
  - **失败，任务不存在** (HTTP 404):
    ```json
    {
      "error": "Task ID not found",
      "code": "TASK_NOT_FOUND"
    }
    ```

- **示例**:
  ```bash
  curl -X POST http://localhost:5000/api/ocr/cancel/550e8400-e29b-41d4-a716-446655440000
  ```

## 错误代码

| HTTP 状态码 | 错误代码              | 描述             |
| ----------- | --------------------- | ---------------- |
| 400         | NO_FILE_UPLOADED      | 没有上传文件     |
| 400         | UNSUPPORTED_FILE_TYPE | 不支持的文件类型 |
| 400         | FILE_TOO_LARGE        | 文件大小超过限制 |
| 400         | INVALID_TASK_ID       | 无效的任务 ID    |
| 404         | TASK_NOT_FOUND        | 任务不存在       |
| 500         | INTERNAL_SERVER_ERROR | 服务器内部错误   |
| 503         | SERVICE_UNAVAILABLE   | 服务暂时不可用   |

## 限制

### 1. 文件限制

- 最大文件大小: 10MB
- 支持的文件类型: PDF, PNG, JPG, JPEG, TIFF
- 文件命名规则: 仅支持字母、数字、下划线和连字符

### 2. 请求限制

- 上传接口: 每分钟最多 100 次请求
- 状态查询: 每分钟最多 1000 次请求
- 批量查询: 每次最多 100 个任务 ID

### 3. OCR 限制

- 语言支持: 中文 (chi_sim) 和英文 (eng)
- 图片分辨率: 最大 4096x4096
- PDF 页数: 最大 100 页

### 4. LLM 限制

- 每个任务最大处理时间: 5 分钟
- PDF 页数: 最大 50 页
- 硅基流动 API 调用频率: 根据 API 提供商限制

### 5. 存储限制

- 结果文件保留时间: 30 天
- 临时文件保留时间: 24 小时
- 单个用户存储配额: 1GB

## 最佳实践

### 1. 文件上传

- 在上传前压缩大文件
- 确保图片清晰度
- 使用合适的文件格式

### 2. 状态查询

- 使用轮询间隔: 建议 5-10 秒
- 实现指数退避算法
- 设置合理的超时时间

### 3. 错误处理

- 实现重试机制
- 记录错误日志
- 提供用户友好的错误信息

### 4. 性能优化

- 使用批量查询接口
- 实现本地缓存
- 合理设置并发请求数

### 5. OCR 与 LLM 选择

- 简单文本识别: 使用 OCR 接口
- 复杂图片或版面: 使用 LLM 接口
- 对时间敏感场景: 使用 OCR 接口
- 对识别质量要求高: 使用 LLM 接口

## 更新日志

### v1.0.0 (2024-03-07)

- 初始版本发布
- 支持基本的文件上传和 OCR 处理
- 提供任务状态查询接口

### v2.0.0 (2024-03-08)

- 添加 LLM 文件处理能力
- 新增 LLM 上传和状态查询接口
- 增强错误处理机制

### v2.1.0 (计划中)

- 添加批量查询接口
- 支持更多文件格式
- 优化 LLM 和 OCR 识别性能

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue
- 发送邮件至: support@example.com
- 访问文档网站: https://docs.example.com/ocr-api
