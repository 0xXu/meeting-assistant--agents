# 多 Agent 智能会议助手

<div align="center">

**企业级 5-Agent 会议全流程自动化系统**

基于 LangGraph + WhisperX + FastAPI 构建

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.x-green.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-red.svg)](https://fastapi.tiangolo.com)
[![uv](https://img.shields.io/badge/uv-managed-purple.svg)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 目录

- [项目简介](#项目简介)
- [系统架构](#系统架构)
- [5个Agent详解](#5个Agent详解)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [Docker部署](#docker部署)
- [API文档](#api文档)
- [项目结构](#项目结构)
- [环境变量](#环境变量)

---

## 项目简介

将一场会议从**录音→纪要→待办→洞察→跟进**的全流程压缩到 3 分钟内自动完成。

**核心能力：**

- 🎙️ **实时转写**：WhisperX 语音识别 + pyannote 说话人分离，准确率 95%+，处理速度 70x 实时
- 📝 **智能纪要**：LLM 自动提取议题、讨论要点、结论、决策，输出结构化 Markdown
- ✅ **待办同步**：自动识别行动项（谁/做什么/截止时间），同步到 Jira Cloud + 飞书任务
- 📊 **会议洞察**：情感分析、发言均衡度、效率评分、关键词提取
- 📤 **会后跟进**：汇聚所有结果，推送飞书群消息，设置截止提醒

---

## 系统架构

```
会议音频流
    │
    ▼
┌─────────────────┐
│ Transcription   │  WhisperX + pyannote-audio
│ Agent           │  语音转写 + 说话人识别
└────────┬────────┘
         │ Fan-out（并行）
    ┌────┴─────┬──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Summary │ │Action  │ │Insight │
│Agent   │ │Agent   │ │Agent   │
│摘要生成│ │待办提取│ │洞察分析│
└────┬───┘ └───┬────┘ └───┬────┘
     │         │          │
     └────┬────┴──────────┘
          │ Fan-in（汇聚）
          ▼
    ┌───────────┐
    │ Follow-up │  飞书推送 + 定时提醒
    │ Agent     │
    └───────────┘
```

**编排模式：Pipeline（串行）+ Fan-out/Fan-in（并行）**

| 模式 | 阶段 | 说明 |
|------|------|------|
| Pipeline | 音频 → 转写 | 必须先完成转写，才能进行后续分析 |
| Fan-out | 转写 → 摘要/待办/洞察 | 三个 Agent 互相独立，并行执行减少总延迟 |
| Fan-in | 三 Agent → 跟进 | 等待所有结果汇聚后统一处理 |

---

## 5个Agent详解

### 1. Transcription Agent — 转写 Agent

**职责**：将音频转换为带说话人标签的文字记录

```
输入: 音频字节流（WAV/MP3）
输出: TranscriptResult
  ├── segments: [{speaker, text, start, end, confidence}, ...]
  ├── full_text: 完整文本
  └── duration_seconds: 音频时长
```

**技术实现：**
- **WhisperX**：比原版 Whisper 快 70x，支持批量推理和精确词级时间戳
- **VAD 预处理**：过滤静音段，降低幻觉率
- **pyannote-audio**：说话人 embedding + 聚类，输出 `SPEAKER_00`、`SPEAKER_01` 标签
- **懒加载**：首次调用时加载模型，避免服务启动慢

**降级策略**：模型加载失败时自动切换到内置演示数据，不阻塞后续 Agent

---

### 2. Summary Agent — 摘要 Agent

**职责**：从转写文本中生成结构化会议纪要

```
输入: transcript_text（纯文本）
输出: MeetingSummary
  ├── title: 会议标题
  ├── participants: 参会人列表
  ├── topics: [{title, discussion_points, conclusion}, ...]
  ├── decisions: 会议决策列表
  └── next_steps: 下一步行动
```

**Prompt 设计**：Few-shot + JSON Schema 约束，强制结构化输出，无法解析时回退到规则引擎提取关键句

---

### 3. Action Agent — 待办 Agent

**职责**：提取行动项并同步到外部系统

```
输入: transcript_text（纯文本）
输出: ActionResult
  └── action_items: [{assignee, task, deadline, priority, jira_key, feishu_id}, ...]
```

**技术实现：**
- LLM 提取三元组（谁 / 做什么 / 截止时间）
- 并行同步到 **Jira Cloud**（创建 Issue）和**飞书任务**
- **幂等性保证**：基于 `meeting_id + task_hash` 去重，防止重复创建
- 优先级映射：`urgent/high/medium/low` → Jira Priority

---

### 4. Insight Agent — 洞察 Agent

**职责**：多维度分析会议质量

```
输入: transcript_text + TranscriptResult
输出: MeetingInsight
  ├── overall_sentiment: positive/neutral/negative
  ├── sentiment_score: 0.0~1.0
  ├── efficiency_score: 0~10
  ├── speaker_stats: [{speaker, duration, ratio, word_count}, ...]
  ├── keywords: 关键词列表
  ├── highlights: 会议亮点
  └── suggestions: 改进建议
```

**效率评分算法**：
```
score = 0.4 × LLM评分 + 0.3 × 发言均衡度 + 0.3 × 时间利用率
```
其中发言均衡度基于基尼系数，时间利用率 = 有效发言时长 / 总时长

---

### 5. Follow-up Agent — 跟进 Agent

**职责**：Fan-in 汇聚所有结果，执行会后动作

- 将摘要 + 待办 + 洞察格式化为 Markdown 报告
- 推送到飞书群（富文本消息）
- 统计 Jira/飞书同步状态
- 为有截止时间的待办设置提醒

---

## 技术栈

| 模块 | 技术 | 版本 |
|------|------|------|
| Agent 编排 | LangGraph | 1.x |
| 语音转写 | WhisperX | 3.x |
| 说话人识别 | pyannote-audio | 4.x |
| LLM 客户端 | MiniMax / OpenAI | - |
| Web 框架 | FastAPI + Uvicorn | 0.115+ |
| 实时通信 | WebSocket | - |
| 向量数据库 | ChromaDB | 0.5+ |
| 关系数据库 | PostgreSQL + asyncpg | 16 |
| 依赖管理 | uv | 0.11+ |
| 日志 | Loguru | 0.7+ |
| 重试机制 | Tenacity | 9.x |

---

## 快速开始

### 前置条件

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)（`curl -LsSf https://astral.sh/uv/install.sh | sh`）
- ffmpeg（`brew install ffmpeg` / `apt install ffmpeg`）

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd meeting-assistant-agents

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 启动服务

```bash
uv run python -m src.main
```

服务启动后：
- **API 文档**：http://localhost:8000/docs
- **WebSocket**：`ws://localhost:8000/ws/meeting/{meeting_id}`

### 演示模式（无需 API Key）

```bash
# 创建会议
curl -X POST http://localhost:8000/api/v1/meeting/start

# 运行演示 Pipeline（使用内置转写数据）
curl -X POST http://localhost:8000/api/v1/meeting/{meeting_id}/demo
```

---

## Docker部署

```bash
# 启动全部服务（API + PostgreSQL + Redis）
docker compose up -d

# 查看日志
docker compose logs -f meeting-assistant

# 停止
docker compose down
```

> **注意**：需要先创建 `.env` 文件，docker compose 会自动注入环境变量。

---

## API文档

详细接口说明见 [docs/api-reference.md](docs/api-reference.md)，或启动服务后访问 http://localhost:8000/docs 查看 Swagger UI。

**主要接口概览：**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/meeting/start` | 创建会议，返回 meeting_id |
| POST | `/api/v1/meeting/{id}/demo` | 演示模式，无需音频 |
| POST | `/api/v1/meeting/{id}/upload` | 上传音频文件 |
| GET | `/api/v1/meeting/{id}/transcript` | 获取转写结果 |
| GET | `/api/v1/meeting/{id}/summary` | 获取会议纪要 |
| GET | `/api/v1/meeting/{id}/actions` | 获取待办事项 |
| GET | `/api/v1/meeting/{id}/insights` | 获取会议洞察 |
| GET | `/api/v1/meeting/{id}/report` | 获取完整报告 |
| WS | `/ws/meeting/{id}` | WebSocket 实时通信 |

---

## 项目结构

```
.
├── src/
│   ├── agents/
│   │   ├── transcription_agent.py   # 转写 Agent
│   │   ├── summary_agent.py         # 摘要 Agent
│   │   ├── action_agent.py          # 待办 Agent
│   │   ├── insight_agent.py         # 洞察 Agent
│   │   └── followup_agent.py        # 跟进 Agent
│   ├── graph/
│   │   └── meeting_graph.py         # LangGraph 编排（Pipeline + 并行）
│   ├── integrations/
│   │   ├── minimax_client.py        # MiniMax LLM
│   │   ├── jira_client.py           # Jira Cloud
│   │   └── feishu_client.py         # 飞书 Open API
│   ├── models/
│   │   └── schemas.py               # 数据模型（dataclass）
│   ├── websocket/
│   │   └── server.py                # FastAPI + WebSocket
│   └── main.py
├── docs/
│   ├── architecture.md              # 架构设计详解
│   └── api-reference.md             # API 参考
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
└── pyproject.toml
```

---

## 环境变量

复制 `.env.example` 为 `.env` 并填入配置。所有外部集成均为**可选**，未配置时服务以演示模式运行。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MINIMAX_API_KEY` | MiniMax API 密钥 | - |
| `MINIMAX_MODEL` | MiniMax 模型名 | `abab6.5s-chat` |
| `OPENAI_API_KEY` | OpenAI API 密钥（备选 LLM） | - |
| `WHISPER_MODEL_SIZE` | Whisper 模型大小 | `large-v2` |
| `WHISPER_DEVICE` | 推理设备 | `cpu` |
| `WHISPER_LANGUAGE` | 转写语言 | `zh` |
| `JIRA_SERVER` | Jira 服务地址 | - |
| `JIRA_EMAIL` | Jira 账号邮箱 | - |
| `JIRA_API_TOKEN` | Jira API Token | - |
| `JIRA_PROJECT_KEY` | Jira 项目 Key | `MEET` |
| `FEISHU_APP_ID` | 飞书应用 ID | - |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | - |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook | - |
| `DATABASE_URL` | PostgreSQL 连接串 | - |
| `SERVER_PORT` | 服务端口 | `8000` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

---

## 容错设计

每个 Agent 均实现独立的降级策略，单个 Agent 失败不影响整体 Pipeline：

| Agent | 降级方案 |
|-------|----------|
| Transcription | 模型不可用 → 内置演示数据 |
| Summary | LLM 失败 → 规则引擎提取关键句 |
| Action | LLM 失败 → 返回空列表，记录错误 |
| Insight | LLM 失败 → 仅输出规则统计（发言时长等） |
| Follow-up | 飞书/Jira 不可用 → 本地生成报告文件 |

---

## License

[MIT](LICENSE)
