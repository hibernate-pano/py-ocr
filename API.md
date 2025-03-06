# Py OCR 服务 API 文档

## 基本信息

- **基础URL**: `http://localhost:5000/api`
- **内容类型**: 请求和响应均使用JSON格式，除非特别说明

## 认证

目前API不需要认证。

## 接口列表

### 1. 上传文件接口

用于上传需要OCR处理的文件。

- **URL**: `/upload`
- **方法**: `POST`
- **内容类型**: `multipart/form-data`
- **参数**:

  | 参数名 | 类型   | 必填 | 描述                      |
  |--------|--------|------|---------------------------|
  | file   | 文件   | 是   | 需要上传的文件，支持PDF和常见图片格式 |

- **响应**:
  - **成功** (HTTP 200):
    ```json
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    ```
  - **失败** (HTTP 400):
    ```json
    {
        "error": "没有上传文件"
    }
    ```
    或
    ```json
    {
        "error": "不支持的文件类型"
    }
    ```
  - **失败** (HTTP 500):
    ```json
    {
        "error": "服务器内部错误"
    }
    ```

- **示例**:
  ```bash
  curl -X POST -F "file=@test.pdf" http://localhost:5000/api/upload
  ```

### 2. 查询任务状态接口

用于获取OCR任务的处理状态和结果。

- **URL**: `/status/<task_id>`
- **方法**: `GET`
- **URL参数**:

  | 参数名  | 类型   | 必填 | 描述      |
  |---------|--------|------|-----------|
  | task_id | 字符串 | 是   | 任务ID    |

- **响应**:
  - **成功，任务处理中** (HTTP 200):
    ```json
    {
        "status": "processing"
    }
    ```
  - **成功，任务已完成** (HTTP 200):
    ```json
    {
        "status": "completed",
        "minio_url": "http://minio.example.com/ocr-results/550e8400-e29b-41d4-a716-446655440000.txt"
    }
    ```
  - **成功，任务失败** (HTTP 200):
    ```json
    {
        "status": "failed",
        "error": "OCR处理失败: 文件损坏"
    }
    ```
  - **失败，任务不存在** (HTTP 404):
    ```json
    {
        "error": "Task ID not found"
    }
    ```

- **示例**:
  ```bash
  curl http://localhost:5000/api/status/550e8400-e29b-41d4-a716-446655440000
  ```

## 错误代码

| HTTP状态码 | 错误描述               |
|------------|------------------------|
| 400        | 请求参数错误           |
| 404        | 资源不存在             |
| 500        | 服务器内部错误         |

## 限制

- 最大文件大小: 10MB
- 支持的文件类型: PDF, PNG, JPG, JPEG, TIFF
- OCR语言: 中文 (chi_sim) 和英文 (eng) 