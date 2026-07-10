# Protocol 通信协议

> 状态: 🧠 概念阶段

## 通信层次

```
Agent ← MCP (stdio) → MCP Server ← HTTP/WS → Unity
```

Agent 只面对 MCP 工具。以下为 MCP Server ↔ Unity 的底层协议。

## HTTP API

### 命令端点

**POST** `http://localhost:3748/cmd`

请求头：
```
Authorization: Bearer {token}
Content-Type: application/json
```

请求体：
```json
{
  "requestId": "req_456",
  "command": "get.data",
  "params": { "dataId": "equipment_03" }
}
```

立即响应（received）：
```json
{
  "requestId": "req_456",
  "status": "received"
}
```

### 错误响应

```json
{
  "requestId": "req_456",
  "status": "error",
  "code": 404,
  "message": "data not found: equipment_xx"
}
```

## WebSocket

### 连接

**GET** `ws://localhost:3748/ws`

鉴权：连接时 URL 参数带 token `?token=xxx`。token 配置见 [Security](Security.md)。

### 命令回执（completed）

```json
{
  "requestId": "req_456",
  "status": "completed",
  "data": {
    "id": "equipment_03",
    "displayName": "显微镜",
    "description": "...",
    "imagePath": "textures/microscope.png"
  }
}
```

### 交互回调

学生在前端触发回调元件时推送：

```json
{
  "requestId": "req_789",
  "inResponseTo": "req_456",   // 触发本次交互的 page.run 命令 requestId
  "event": "interaction",
  "pageId": "page_1",
  "elementId": "elem_3",
  "action": "submitted",
  "data": {
    "questionId": "question_07",
    "answer": "B",
    "timestamp": 1750000000
  }
}
```

### 系统事件

| 事件 | 说明 |
|:--|:--|
| `page.rendered` | 页面渲染完成 |
| `page.error` | 页面渲染错误 |
| `dialog.timeout` | 对话超时 |
| `system.error` | 系统内部错误 |

## 回执机制

两条原则：
1. 回执只推状态码，不夹带数据
2. Agent 需要数据时主动 `get.data`

```
HTTP: received (毫秒级) → Agent 可继续发下一条
WS:   completed (执行完后) → Agent 知道命令执行结束
```

Agent 决策循环：发命令 → 收到 received → 发下一条 → ... → 收到 completed → 处理结果。

## 超时与重试

- HTTP 请求超时：5 秒
- 命令执行超时：30 秒（可配置 `COMMAND_TIMEOUT`）
- 超时未收到 completed 则 MCP Server 返回超时错误
- WebSocket 断开后 MCP Server 自动重连。重连后 MCP Server 主动发 `result.get` 拉取断连期间未回执的命令结果。Unity 侧对已完成的 requestId 进行幂等去重（保留最近 100 条），确保不重复执行

### requestId 格式

`req_` 前缀 + UUID 前 8 位，如 `req_a1b2c3d4`。由 MCP Server 生成，HTTP received 和 WS completed 使用同一 ID 匹配。

## 降级说明

Embedding 不可用时 `search.data` 回退为关键词匹配（displayName + description 全文搜索），Agent 同样获得 ID 列表但无 `knowledgeOriginal` 和 `score` 字段。LM Studio 不可用不影响其他命令。
