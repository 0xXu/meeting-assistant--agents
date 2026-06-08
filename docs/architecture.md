# 架构设计详解

## 1. 整体架构

### 1.1 系统分层

```
┌─────────────────────────────────────────┐
│           接入层 (Gateway)               │
│     REST API / WebSocket / Webhook      │
├─────────────────────────────────────────┤
│           编排层 (Orchestration)         │
│           LangGraph StateGraph          │
├─────────────────────────────────────────┤
│              Agent 层                   │
│  Transcription / Summary / Action /     │
│       Insight / Follow-up               │
├─────────────────────────────────────────┤
│           集成层 (Integration)           │
│    LLM API / Jira / 飞书 / WhisperX    │
├─────────────────────────────────────────┤
│           数据层 (Storage)               │
│      PostgreSQL / ChromaDB / Redis      │
└─────────────────────────────────────────┘
```

### 1.2 编排模式

本系统采用 **Pipeline + 并行（Fan-out / Fan-in）** 混合编排：

```
START → [Transcription] → Fan-out → [Summary | Action | Insight] → Fan-in → [Follow-up] → END
```

| 模式 | 优点 | 适用场景 |
|------|------|----------|
| Pipeline（串行） | 简单可靠，前后依赖明确 | 音频 → 转写（必须先转写） |
| Fan-out（并行） | 减少总延迟，独立 Agent 互不干扰 | 摘要 / 待办 / 洞察（互相独立） |
| Fan-in（汇聚） | 等待所有结果后统一处理 | 跟进 Agent 需要所有数据 |

## 2. 数据流设计

### 2.1 状态驱动架构

所有 Agent 共享一个 `MeetingState` 字典，由 LangGraph 在节点间传递：

```python
MeetingState = {
    "meeting_id":      str,              # 全局标识
    "status":          MeetingStatus,    # 当前阶段
    "audio_data":      bytes,            # 输入音频
    "transcript":      TranscriptResult, # TranscriptionAgent 写入
    "transcript_text": str,              # TranscriptionAgent 写入
    "summary":         MeetingSummary,   # SummaryAgent 写入（并行）
    "actions":         ActionResult,     # ActionAgent 写入（并行）
    "insights":        MeetingInsight,   # InsightAgent 写入（并行）
    "followup":        FollowUpResult,   # FollowUpAgent 写入
    "errors":          list[str],        # 所有 Agent 均可追加
}
```

**关键设计决策：**
- 每个 Agent 只读自己需要的字段，只写自己负责的字段
- 并行 Agent 写入不同字段，天然避免冲突
- 错误追加到 `errors` 列表，不中断 Pipeline

### 2.2 并行安全

LangGraph 负责 Fan-out 并行调度与 Fan-in 状态合并，各并行节点写入不同 key，无需额外锁机制。

## 3. 容错设计

### 3.1 Agent 级别容错

每个 Agent 的 `process()` 方法统一遵循以下模式：

```python
async def process(self, state: dict) -> dict:
    try:
        # 执行核心逻辑
        ...
    except Exception as e:
        state["errors"].append(f"AgentName: {e}")
        state["field"] = fallback_result   # 写入降级结果
    return state  # 永远不抛异常，不中断 Pipeline
```

### 3.2 降级策略

| Agent | 降级方案 |
|-------|----------|
| Transcription | 模型加载失败 → 使用内置演示转写数据 |
| Summary | LLM 调用失败 → 规则引擎提取关键句 |
| Action | LLM 失败 → 返回空待办列表，记录错误 |
| Insight | LLM 失败 → 仅输出规则统计结果（发言时长等） |
| Follow-up | 飞书 / Jira 不可用 → 本地生成报告文件 |

### 3.3 重试机制

使用 `tenacity` 实现指数退避重试：
- 退避策略：1s → 2s → 4s
- 最大重试：3 次
- 仅对可重试错误（网络超时、限流 429）重试

## 4. 可扩展性

### 4.1 新增 Agent

1. 在 `src/agents/` 创建新 Agent 类，实现 `async def process(state: dict) -> dict`
2. 在 `src/models/schemas.py` 添加对应输出数据模型
3. 在 `src/graph/meeting_graph.py` 注册节点并定义边

### 4.2 水平扩展

- Agent 无状态 → 可多实例部署
- 消息队列解耦 → Redis / RabbitMQ
- 会议状态持久化 → PostgreSQL

## 5. 监控与可观测性

### 5.1 日志规范

每个 Agent 统一使用 loguru，格式为：

```
[AgentName] action: meeting_id, detail
```

### 5.2 关键指标

| 指标 | 采集方式 |
|------|----------|
| Pipeline 总耗时 | 入口 / 出口时间差 |
| 各 Agent 耗时 | 节点执行前后时间戳 |
| LLM 调用次数 / 延迟 | HTTP 客户端中间件 |
| 错误率 | `state["errors"]` 统计 |
| Jira / 飞书同步成功率 | 集成客户端内部统计 |
