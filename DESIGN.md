# Py OCR 服务设计文档

## 1. 系统架构

### 1.1 整体架构

```
+-------------+     +-------------+     +--------------+
|             |     |             |     |              |
| Client/用户  +---->+ Flask API   +---->+ Celery Queue |
|             |     |             |     |              |
+-------------+     +-------------+     +--------------+
                          |                    |
                          v                    v
                   +-----------+        +-------------+
                   |           |        |             |
                   | SQLite DB |        | OCR Worker  |
                   |           |        | LLM Worker  |
                   +-----------+        | Ollama Worker|
                                        +-------------+
                                             |
                                             v
                                    +----------------+     +---------------+     +----------------+
                                    |                |     |               |     |                |
                                    | MinIO Storage  |     | 硅基流动 API   |     | Ollama API     |
                                    |                |     |               |     |                |
                                    +----------------+     +---------------+     +----------------+
```

### 1.2 核心组件

- **Flask API**: 提供 RESTful API 接口
- **Celery Queue**: 异步任务队列
- **SQLite DB**: 存储任务状态和结果
- **OCR Worker**: 处理 OCR 识别任务
- **LLM Worker**: 处理多模态大模型识别任务
- **Ollama Worker**: 处理基于 Ollama 的本地多模态模型识别任务
- **MinIO Storage**: 对象存储服务
- **硅基流动 API**: 提供多模态大模型服务
- **Ollama API**: 提供本地部署的多模态模型服务

### 1.3 技术栈选型理由

- **Flask**: 轻量级、灵活、易于扩展
- **Celery**: 分布式任务队列，支持异步处理和任务重试
- **SQLite**: 无需额外服务器，适合中小规模应用
- **MinIO**: 兼容 S3 协议，支持分布式部署
- **Tesseract**: 开源 OCR 引擎，支持多语言
- **多模态大模型**: 通过硅基流动 API 调用，提供更高精度的图像理解和文本识别能力
- **Ollama**: 本地部署的多模态大模型，支持离线处理，适合对数据隐私要求高的场景

## 2. 项目结构

### 2.1 目录结构

```
py-ocr/
├── app/                    # 应用主目录
│   ├── api/               # API接口层
│   │   ├── __init__.py
│   │   └── routes.py     # API路由定义
│   ├── config/           # 配置层
│   │   ├── __init__.py
│   │   ├── config.py    # 配置类
│   │   └── logging_config.py  # 日志配置
│   ├── models/           # 数据模型层
│   │   ├── __init__.py
│   │   └── task.py      # 任务模型
│   ├── services/         # 服务层
│   │   ├── __init__.py
│   │   ├── minio_service.py  # MinIO服务
│   │   ├── ocr_service.py    # OCR服务
│   │   ├── llm_service.py    # LLM服务
│   │   └── ollama_ocr_service.py # Ollama OCR服务
│   ├── tasks/            # 任务层
│   │   ├── __init__.py
│   │   ├── ocr_task.py  # OCR Celery任务
│   │   ├── llm_task.py  # LLM Celery任务
│   │   └── ollama_ocr_task.py # Ollama OCR Celery任务
│   └── utils/           # 工具层
│       └── __init__.py
├── tests/               # 测试目录
├── docs/               # 文档目录
└── deployment/         # 部署配置
```

### 2.2 分层设计

1. **表现层 (API 层)**

   - 处理 HTTP 请求和响应
   - 参数验证和错误处理
   - 路由管理

2. **业务层 (Service 层)**

   - 实现核心业务逻辑
   - 组合调用各种服务
   - 事务管理

3. **数据层 (Model 层)**

   - 数据结构定义
   - 数据访问接口
   - 数据验证逻辑

4. **任务层 (Task 层)**
   - 异步任务定义
   - 任务状态管理
   - 重试策略

## 3. 设计原则

### 3.1 SOLID 原则应用

1. **单一职责原则 (SRP)**

   - OCRService 专注于文本识别
   - LLMService 专注于多模态大模型识别
   - MinioService 专注于文件存储
   - TaskService 专注于任务管理

2. **开放封闭原则 (OCP)**

   - 服务接口抽象化
   - 配置外部化
   - 插件化设计

3. **里氏替换原则 (LSP)**

   - 文件处理接口统一
   - 存储服务接口统一
   - 任务处理接口统一

4. **接口隔离原则 (ISP)**

   - 最小化服务接口
   - 职责明确的 API
   - 解耦的组件设计

5. **依赖倒置原则 (DIP)**
   - 依赖抽象而非实现
   - 通过配置注入依赖
   - 使用工厂模式创建实例

### 3.2 设计模式应用

1. **创建型模式**

   - 单例模式: 配置管理、数据库连接
   - 工厂模式: 服务创建、任务创建
   - 建造者模式: 复杂对象构建

2. **结构型模式**

   - 适配器模式: 统一接口适配
   - 装饰器模式: 功能增强
   - 代理模式: 访问控制

3. **行为型模式**
   - 策略模式: 文件处理策略
   - 观察者模式: 任务状态通知
   - 命令模式: 任务执行

## 4. 关键流程

### 4.1 文件上传流程

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Validator
    participant Storage
    participant Queue

    Client->>API: 上传文件
    API->>Validator: 验证文件
    Validator-->>API: 验证结果
    API->>Storage: 保存临时文件
    API->>Queue: 创建OCR/LLM任务
    API-->>Client: 返回任务ID
```

### 4.2 OCR 处理流程

```mermaid
sequenceDiagram
    participant Queue
    participant Worker
    participant OCR
    participant Storage
    participant DB

    Queue->>Worker: 获取任务
    Worker->>OCR: 处理文件
    OCR->>Storage: 保存结果
    Storage-->>Worker: 返回URL
    Worker->>DB: 更新状态
```

### 4.3 LLM 处理流程

```mermaid
sequenceDiagram
    participant Queue
    participant Worker
    participant LLMService
    participant SiliconFlowAPI
    participant Storage
    participant DB

    Queue->>Worker: 获取任务
    Worker->>LLMService: 处理文件
    LLMService->>SiliconFlowAPI: 调用多模态API
    SiliconFlowAPI-->>LLMService: 返回识别结果
    LLMService->>Storage: 保存结果
    Storage-->>Worker: 返回URL
    Worker->>DB: 更新状态
```

### 4.4 Ollama OCR 处理流程

```mermaid
sequenceDiagram
    participant Queue
    participant Worker
    participant OllamaOCRService
    participant OllamaAPI
    participant Storage
    participant DB

    Queue->>Worker: 获取任务
    Worker->>OllamaOCRService: 处理文件
    OllamaOCRService->>OllamaAPI: 调用多模态API
    OllamaAPI-->>OllamaOCRService: 返回识别结果
    OllamaOCRService->>Storage: 保存结果
    Storage-->>Worker: 返回URL
    Worker->>DB: 更新状态
```

## 5. 安全设计

### 5.1 系统安全

- 输入验证
- CORS 配置
- 请求限流
- 文件大小限制
- API 密钥管理

### 5.2 数据安全

- 文件名加密
- 临时文件清理
- MinIO 访问控制
- 数据备份策略
- 敏感信息加密

## 6. 性能优化

### 6.1 系统优化

- 异步处理
- 任务队列
- 连接池
- 缓存策略

### 6.2 OCR 优化

- 图像预处理
- 并行处理
- 结果缓存
- 批量处理

### 6.3 LLM 优化

- 请求批处理
- 结果缓存
- 超时重试策略
- 错误恢复机制

## 7. 可用性设计

### 7.1 高可用方案

- 服务冗余
- 负载均衡
- 故障转移
- 数据备份

### 7.2 监控告警

- 系统监控
- 性能监控
- 错误告警
- 日志分析

## 8. 扩展性设计

### 8.1 水平扩展

- 多 Worker 部署
- 分布式存储
- 负载均衡
- 数据分片

### 8.2 垂直扩展

- 资源配置优化
- 代码优化
- 算法优化
- 缓存优化

## 9. 部署方案

### 9.1 Docker 部署

```yaml
version: "3"
services:
  web:
    build: .
    ports:
      - "5000:5000"
  worker:
    build: .
    command: celery worker
  redis:
    image: redis:latest
  minio:
    image: minio/minio
```

### 9.2 Kubernetes 部署

- 资源配置
- 服务编排
- 自动扩缩容

## 10. 开发规范

### 10.1 代码规范

- 遵循 PEP 8
- 类型注解
- 文档字符串
- 单元测试

### 10.2 Git 规范

- 分支管理
- 提交信息
- 代码审查
- 版本发布

## 11. 测试策略

### 11.1 单元测试

- 服务层测试
- 模型层测试
- 工具函数测试
- 边界条件测试

### 11.2 集成测试

- API 测试
- 任务处理测试
- 存储服务测试
- 性能测试

### 11.3 端到端测试

- 完整流程测试
- 异常场景测试
- 压力测试
- 兼容性测试

## 12. 监控和运维

### 12.1 监控指标

- 请求量
- 响应时间
- 错误率
- 资源使用率

### 12.2 日志管理

- 访问日志
- 错误日志
- 性能日志
- 审计日志

### 12.3 告警策略

- 错误率告警
- 性能告警
- 资源告警
- 安全告警

## 13. 版本规划

### 13.1 v1.0.0

- 基础功能实现
- 核心 API 完成
- 基本测试覆盖

### 13.2 v1.1.0

- 批量处理优化
- 更多文件格式支持
- 性能优化

### 13.3 v1.2.0

- 认证授权
- 高级 OCR 功能
- 分布式部署支持

### 13.4 v2.0.0

- 多模态 LLM 集成
- 双路识别引擎
- 更丰富的图像理解能力

## 14. 风险评估

### 14.1 技术风险

- OCR 准确率
- LLM 响应时间
- 系统性能
- 数据安全
- 服务可用性

### 14.2 业务风险

- 用户需求变化
- 市场竞争
- 成本控制
- 合规要求

## 15. 维护计划

### 15.1 日常维护

- 日志清理
- 数据备份
- 性能监控
- 安全更新

### 15.2 定期优化

- 代码重构
- 性能调优
- 功能增强
- 文档更新

## 16. 硅基流动 API 集成

### 16.1 API 请求流程

1. **认证授权**

   - 使用 API 密钥进行认证
   - JWT 令牌获取
   - 权限校验

2. **请求格式**

   - 图像 Base64 编码
   - 上传图像文件
   - 请求参数配置

3. **响应处理**
   - 结果解析
   - 错误处理
   - 重试机制

### 16.2 服务质量保障

1. **性能监控**

   - 调用延迟
   - 并发请求
   - 错误率

2. **资源管理**

   - 并发控制
   - 流量控制
   - 资源配额

3. **降级策略**
   - API 不可用时自动降级
   - 超时处理
   - 备用方案

## 17. Ollama 集成

### 17.1 Ollama 简介

Ollama 是一个轻量级的框架，允许在本地运行各种大型语言模型 (LLMs)，包括 Llama 2、LLaVA (多模态模型) 等。通过 Ollama，我们可以在本地部署和运行多模态模型，无需依赖外部 API 服务。

### 17.2 Ollama 功能

1. **本地运行多模态模型**

   - 支持 LLaVA 等多模态模型
   - 本地处理图像和提取文本
   - 保护数据隐私和安全

2. **API 调用方式**

   - RESTful API 接口
   - 支持图像 base64 编码传输
   - 支持自定义提示词和参数

3. **批量处理能力**
   - 支持 PDF 文件分页处理
   - 自动合并多页结果
   - 任务状态管理和取消

### 17.3 Ollama 集成架构

1. **服务层**

   - OllamaOCRService 类封装 Ollama API 调用
   - 提供任务管理和取消能力
   - 处理不同文件类型 (PDF、图像)

2. **任务层**

   - Celery 异步任务处理
   - 任务重试和错误恢复
   - 结果存储和状态更新

3. **API 层**
   - 提供 `/ocr/upload` 接口
   - 任务状态查询接口
   - 任务取消接口

### 17.4 Ollama 与其他 OCR 引擎对比

| 功能         | Ollama OCR         | Tesseract OCR      | 硅基流动 API       |
| ------------ | ------------------ | ------------------ | ------------------ |
| 部署方式     | 本地/私有云        | 本地/私有云        | 云服务             |
| 处理性能     | 依赖硬件           | 快                 | 快                 |
| 识别精度     | 高                 | 中等               | 高                 |
| 离线工作     | 支持               | 支持               | 不支持             |
| 数据隐私     | 较好               | 好                 | 一般               |
| 系统资源需求 | 高 (GPU)           | 低                 | 低                 |
| 适用场景     | 复杂文档、私有数据 | 简单文档、批量处理 | 高精度需求、低延迟 |

### 17.5 Ollama 部署建议

1. **硬件建议**

   - CPU: 4 核以上
   - RAM: 16GB 以上
   - GPU: NVIDIA GPU 8GB+显存 (推荐)
   - 存储: SSD 50GB+

2. **模型选择**

   - 文本识别: LLaVA (推荐)
   - 其他选项: BakLLaVA, llava-13b

3. **性能优化**
   - 调整批处理大小
   - 设置合理的超时时间
   - 使用 GPU 加速
