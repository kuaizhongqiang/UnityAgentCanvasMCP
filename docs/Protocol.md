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

### 数据导出端点

**GET** `http://localhost:3748/data/export`

返回 Unity 内存中所有 DataBase 数据的 JSON 序列化结果，供 Embedding 引擎构建索引。每次调用返回当前最新数据。

```json
{
  "version": 1,
  "exportedAt": "2026-07-10T12:00:00Z",
  "count": 100,
  "items": [
    {
      "id": "equipment_03",
      "displayName": "显微镜",
      "description": "光学显微镜构造与成像原理",
      "tag": ["显微镜", "光学", "成像"],
      "data": {
        "imagePath": "textures/microscope.png",
        "modelId": "model_microscope_01"
      },
      "templateType": "image_text"
    }
  ]
}
```

| 字段 | 来源 | 说明 |
|:--|:--|:--|
| `id` | DataBase.id | 唯一标识 |
| `displayName` | DataBase.displayName | 显示名称 |
| `description` | DataBase.description | 描述文本 |
| `tag` | 数据编辑器配置 | 关键词标签 |
| `data` | DataBase 子类自定义 | 子类特定字段（imagePath, modelId 等） |
| `templateType` | 数据编辑器配置 | 建议 UI 模板类型 |

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
  "inResponseTo": "req_456",
  "event": "interaction",
  "dialogId": "dialog_1",
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
- WebSocket 断开后 MCP Server 自动重连。重连后 MCP Server 调用 `status.list {dialogId}` 查询所有请求状态：
  - `completed` → 直接返回结果给 Agent
  - `failed` → 返回错误
  - `pending` → 继续等待 WS completed
- Unity 侧对所有 requestId 进行幂等去重（保留最近 100 条，覆盖 pending/completed/failed 全部状态），确保不重复执行

### requestId 格式

`req_` 前缀 + UUID 前 8 位，如 `req_a1b2c3d4`。由 MCP Server 生成，HTTP received 和 WS completed 使用同一 ID 匹配。

## 降级说明

Embedding 不可用时 `search.data` 回退为关键词匹配（displayName + description 全文搜索），Agent 同样获得 ID 列表但无 `knowledgeOriginal` 和 `score` 字段。LM Studio 不可用不影响其他命令。
