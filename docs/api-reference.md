# API 参考文档

交互式文档（Swagger UI）：启动服务后访问 **http://localhost:8000/docs**

---

## REST API

所有接口基础路径：`/api/v1`

### 创建会议

```http
POST /api/v1/meeting/start
```

**响应示例**
```json
{
  "meeting_id": "abc123",
  "websocket_url": "ws://localhost:8000/ws/meeting/abc123",
  "status": "created"
}
```

---

### 演示模式（无需音频）

```http
POST /api/v1/meeting/{meeting_id}/demo
```

触发完整的 5-Agent Pipeline，使用内置演示转写数据，无需配置任何 API Key。

**响应**：完整会议处理结果（转写 + 摘要 + 待办 + 洞察 + 跟进）

---

### 上传音频

```http
POST /api/v1/meeting/{meeting_id}/upload
Content-Type: multipart/form-data
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `file` | File | 音频文件（支持 .wav / .mp3 / .m4a） |

---

### 获取转写结果

```http
GET /api/v1/meeting/{meeting_id}/transcript
```

---

### 获取会议纪要

```http
GET /api/v1/meeting/{meeting_id}/summary
```

---

### 获取待办事项

```http
GET /api/v1/meeting/{meeting_id}/actions
```

---

### 获取会议洞察

```http
GET /api/v1/meeting/{meeting_id}/insights
```

---

### 获取完整报告

```http
GET /api/v1/meeting/{meeting_id}/report
```

---

## WebSocket API

### 连接

```
ws://localhost:8000/ws/meeting/{meeting_id}
```

### 客户端 → 服务端（发送消息）

| `type` | 说明 |
|--------|------|
| `start` | 开始录制 |
| `stop` | 停止录制，触发 Pipeline 处理 |
| `demo` | 运行演示模式 |
| `ping` | 心跳保活 |

```json
{"type": "start"}
{"type": "stop"}
{"type": "demo"}
{"type": "ping"}
```

### 服务端 → 客户端（接收消息）

| `type` | 说明 |
|--------|------|
| `connected` | 连接建立 |
| `recording` | 正在录制，含缓冲大小 |
| `processing` | Pipeline 处理中 |
| `transcript` | 转写结果就绪 |
| `summary` | 会议纪要就绪 |
| `actions` | 待办事项就绪 |
| `insights` | 会议洞察就绪 |
| `completed` | 全部处理完成 |
| `error` | 出现错误 |

```json
{"type": "connected", "meeting_id": "abc123"}
{"type": "recording", "buffer_size": 1024}
{"type": "processing", "message": "转写中..."}
{"type": "transcript", "data": { "segments": [...], "full_text": "..." }}
{"type": "summary", "data": { "title": "...", "topics": [...] }}
{"type": "actions", "data": { "action_items": [...] }}
{"type": "insights", "data": { "efficiency_score": 8.5, "keywords": [...] }}
{"type": "completed", "meeting_id": "abc123"}
{"type": "error", "message": "..."}
```
