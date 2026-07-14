# AI 赋能的智能简历分析系统

基于 AI 的智能简历解析与岗位匹配系统。上传 PDF 简历，自动提取关键信息，并与招聘岗位需求进行智能匹配评分。

## 功能特性

- **📄 简历解析** — 支持多页 PDF 简历上传，自动提取文本
- **🔍 信息提取** — 基于 AI 识别姓名、电话、邮箱、学历、技能、项目经历等
- **🎯 智能匹配** — 将简历与岗位描述进行多维度匹配评分（技能、经验、学历）
- **⚡ 缓存加速** — 内置缓存机制，避免重复计算
- **🖥 可视化界面** — 简洁的前端交互页面，三步完成分析

## 技术架构

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Frontend   │────▶│  FastAPI Backend  │────▶│  AI Model   │
│  GitHub Pages│     │  (Alibaba Cloud FC)│    │  (LLM API)  │
└──────────────┘     └────────┬─────────┘     └─────────────┘
                              │
                     ┌────────▼─────────┐
                     │  Cache (Memory    │
                     │   or Redis)      │
                     └──────────────────┘
```

### 技术选型

| 层级       | 技术                          | 说明                           |
| -------- | --------------------------- | ---------------------------- |
| **后端**   | Python + FastAPI            | 高性能异步 RESTful API           |
| **PDF 解析** | PyMuPDF + pdfplumber 双引擎 | 中文兼容性好，支持多页，图片 PDF 兜底    |
| **AI 模型** | 兼容 OpenAI 接口的 LLM（可配置）     | 通义千问/DeepSeek/GPT 等          |
| **缓存**   | 内存缓存 + 可选 Redis            | 单实例用内存缓存,分布式用 Redis         |
| **前端**   | 原生 HTML/CSS/JS             | 零依赖，直接部署 GitHub Pages       |
| **部署**   | 阿里云函数计算 FC / Docker       | 支持 Serverless 部署             |

## 项目结构

```
├── backend/                   # 后端服务
│   ├── main.py                # FastAPI 应用入口 + API 路由
│   ├── config.py              # 环境配置（AI Key、缓存、上传限制）
│   ├── models.py              # Pydantic 数据模型
│   ├── pdf_parser.py          # PDF 解析模块
│   ├── text_processor.py      # 文本清洗与分段
│   ├── info_extractor.py      # AI 信息提取（含规则 fallback）
│   ├── matcher.py             # 简历-JD 匹配评分
│   ├── cache.py               # 缓存管理（内存/Redis）
│   └── requirements.txt       # Python 依赖
├── frontend/                  # 前端页面
│   ├── index.html             # 主页面
│   ├── style.css              # 样式
│   └── app.js                 # 交互逻辑
├── .env.example               # 环境变量示例
└── README.md                  # 本文件
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.10+
python --version

# 克隆项目
git clone <your-repo-url>
cd ai-resume-analyzer
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 AI API Key
```

关键配置项：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `AI_API_BASE_URL` | AI API 地址 | `https://api.openai.com/v1` |
| `AI_API_KEY` | AI API 密钥 | `sk-your-api-key` |
| `AI_MODEL` | 模型名称 | `gpt-4o-mini` |
| `CACHE_TYPE` | 缓存类型 | `memory` |
| `REDIS_URL` | Redis 地址(选填) | `redis://localhost:6379/0` |

### 4. 启动后端

```bash
cd backend
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

### 5. 启动前端

```bash
cd frontend
python -m http.server 3000
# 访问 http://localhost:3000
```

> **注意**：前端默认连接 `http://localhost:8000`，部署时需修改 `app.js` 中的 `API_BASE`。

## API 接口

### POST /api/upload
上传 PDF 简历文件。

- **请求**：`multipart/form-data`，字段 `file`（PDF 文件）
- **响应**：`{ resume_id, filename, text_preview }`

### POST /api/analyze/{resume_id}
对已上传的简历进行 AI 信息提取和岗位匹配。

- **请求**：`{ job_description: string }`
- **响应**：`{ resume_id, status, resume_info, match_result }`

### GET /api/health
健康检查。

## 部署指南

### 后端：阿里云函数计算 FC

1. **通过阿里云控制台创建函数**
   - 运行时：Python 3.10+
   - 内存：512MB+
   - 超时时间：120 秒

2. **安装依赖层**
   ```bash
   pip install -r requirements.txt -t ./python
   zip -r layer.zip python/
   ```
   将 `layer.zip` 上传为层。

3. **配置环境变量**
   在函数配置中设置 `AI_API_KEY` 等环境变量。

4. **配置 API 网关**
   为函数创建 HTTP 触发器，获取公网访问地址。

### 前端：GitHub Pages

1. Push 代码到 GitHub 仓库
2. 修改 `frontend/app.js` 中的 `API_BASE` 为后端实际地址
3. 进入仓库 Settings → Pages
4. Source 选择 `main` 分支，目录选择 `/frontend`
5. 保存后获取访问地址

## 设计说明

### AI 降级策略

系统设计了完善的降级机制：
- **信息提取**：AI 提取失败时，自动切换为正则规则提取（覆盖姓名、电话、邮箱、学历等）
- **匹配评分**：AI 匹配失败时，自动切换为关键词规则匹配
- 确保即使 AI API 不可用，核心功能仍可运行

### 缓存策略

- **内存缓存**（默认）：适合单实例开发和调试
- **Redis 缓存**（可选）：适合 Serverless 多实例环境，避免冷启动重复计算
- 缓存 Key = `resume:analysis:<content_hash>`，基于简历内容和 JD 的 SHA256

### 评分维度

综合评分由三个维度加权计算：
- **技能匹配率**（50%）：简历技能与 JD 要求的关键词匹配比例
- **经验相关性**（25%）：工作年限与 JD 要求的匹配程度
- **学历匹配度**（25%）：最高学历是否满足 JD 最低要求

## 许可证

MIT
