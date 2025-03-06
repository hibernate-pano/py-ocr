
**项目名称:** Py OCR 服务

**项目目标:** 构建一个基于 Flask、Tesseract 和 Minio 的 OCR 服务，提供 API 接口供外部调用，将 PDF 文件、图片等转换为文本并存储到 Minio，用户可以通过 API 获取处理状态和结果 URL。

**技术选型:**

- **后端框架:** Flask (最新稳定版)
- **OCR 引擎:** Tesseract (最新版本, 需安装中文语言包 tesseract-ocr-chi_sim)
- **对象存储:** Minio
- **异步任务队列:** Celery + Redis
- **数据存储:** SQLite (或 Redis, 或 Flask-Caching 用于简单状态存储)
- **编程语言:** Python

**功能需求:**

1. **文件上传接口 (/upload):**
	- 接收 multipart/form-data 格式的 POST 请求，包含一个名为 file 的文件字段。
	- 验证文件类型和大小 (例如，限制最大文件大小为 10MB)。
	- 生成唯一的任务 ID (例如 UUID)。
	- 将文件保存到临时目录。
	- 将 OCR 任务放入 Celery 任务队列进行异步处理。
	- 返回包含 task_id 的 JSON 响应 (HTTP 200 OK)。
	- 文件上传失败或参数错误时，返回包含错误信息的 JSON 响应 (HTTP 400/500)。
2. **状态查询接口 (/get/{task_id}):**
	- 接收 GET 请求，URL 路径参数为 task_id。
	- 查询任务状态 (存储在数据库或缓存中)。
	- 如果任务状态为 "processing"，返回 JSON 响应 { "status": "processing" } (HTTP 200 OK)。
	- 如果任务状态为 "completed"，返回 JSON 响应 { "status": "completed", "minio_url": "Minio 文件 URL" } (HTTP 200 OK)。
	- 如果任务状态为 "failed"，返回 JSON 响应 { "status": "failed", "error": "详细错误信息" } (HTTP 200 OK)。
	- 如果 task_id 不存在，返回 JSON 响应 { "error": "Task ID not found" } (HTTP 404 Not Found)。
3. **OCR 处理任务 (Celery Task):**
	- 从任务队列中获取任务 (包含 task_id 和文件路径)。
	- 使用 Tesseract 对文件进行 OCR 识别，提取文本内容。 (默认语言为中文和英文，可考虑后续支持用户指定语言)
	- 将 OCR 结果 (文本) 上传到 Minio 指定 Bucket，文件名使用 task_id.txt。
	- 生成 Minio 文件的可公开访问 URL (或预签名 URL)。
	- 更新任务状态为 "completed"，并将 Minio URL 存储到数据库或缓存中。
	- 如果 OCR 识别或 Minio 上传失败，更新任务状态为 "failed"，并记录错误信息。
4. **错误处理和日志:**
	- 详细记录文件上传、OCR 处理、Minio 上传等关键步骤的日志 (使用 INFO 级别记录正常流程，使用 ERROR 级别记录错误)。
	- 捕获文件上传、OCR 识别、Minio 上传等环节的异常，并进行处理 (例如，返回错误信息给用户，记录错误日志，重试机制 (可选))。
5. **Minio 存储:**
	- 使用指定的 Minio Bucket 存储 OCR 结果。
	- 生成的 Minio URL 需要保证对外可访问 (根据实际 Minio 配置选择合适的访问策略)。

**API 接口定义 (详细):** (参考上面 "API 接口定义" 部分)

**数据存储:** (参考上面 "数据存储" 部分，选择 SQLite 或 Redis 或 Flask-Caching)

**部署和运维:** (初步考虑 Docker 容器化部署)

**其他:**

- 提供简单的 API 文档。
- 编写基本的单元测试和集成测试。
