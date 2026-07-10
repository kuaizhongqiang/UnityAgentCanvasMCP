# MCP Tools 工具接口

> 状态: 🧠 概念阶段

## 概述

MCP Server 将所有 CLI 命令暴露为 MCP 工具。Agent 只调用工具，不接触底层命令格式。

命名映射：CLI 命令用点号（如 `search.data`），MCP 工具用下划线（如 `search_data`）。底层协议见 [Protocol](Protocol.md)。

MCP Server 复用 `cli_core.py`，仅包装为 MCP 协议（stdio 传输）。

## 工具列表

### 帮助类

| 工具 | 参数 | 返回 |
|:--|:--|:--|
| `help` | — | 所有命令列表和用法 |
| `docs` | — | 文档清单 |
| `docs_get` | `name: string` | 文档全文 |

### 查询类

| 工具 | 参数 | 返回 |
|:--|:--|:--|
| `whoami` | — | Agent 身份信息 |
| `dialog_list` | — | 对话列表 |
| `dialog_get` | `dialogId: string` | 对话详情 |
| `page_list` | — | 页面列表 |
| `list_templates` | — | 模板清单 |
| `search_data` | `query: string` | Top-N 搜索结果（含 knowledgeOriginal） |
| `get_data` | `dataId: string` | 数据全文 |
| `usage` | — | 统计数据 |

### 页面操作类

| 工具 | 参数 | 返回 |
|:--|:--|:--|
| `page_create` | `pageId: string` | pageId 确认 |
| `run` | `pageId: string` | requestId → 执行结果 |
| `run_file` | `pageId: string, filePath: string` | requestId → 执行结果 |
| `update` | `pageId: string, patch: object` | requestId → 执行结果 |
| `clear` | `pageId: string, scope?: string` | requestId → 执行结果 |
| `result_show` | `pageId: string, elementId: string, result: object` | requestId → 执行结果 |
| `page_delete` | `pageId: string` | 确认 |
| `stop` | — | 确认 |

### 队列类

| 工具 | 参数 | 返回 |
|:--|:--|:--|
| `queue_list` | — | 队列中的命令列表 |
| `queue_push` | `commands: array` | 各命令 requestId |
| `queue_get` | `commandId: string` | 命令状态 |

### 配置类

| 工具 | 参数 | 返回 |
|:--|:--|:--|
| `init` | `config: object` | 确认（持久化） |
| `restart` | — | 确认 |

## MCP Server 内部流程

```
Agent 调用工具
  → MCP Server 解析参数
    → 生成 requestId
    → POST HTTP 到 Unity
      → 收到 received，返回 Agent（可继续其他操作）
    → 等待 WS completed
      → 返回 Agent 最终结果
```

Agent 调一次工具即获得完整流程（received + completed），无需手动管理 requestId。

## 后续细化

- 每个工具的 JSON Schema 正式定义
- 错误处理策略（重试次数、降级路径）
- 流式响应支持（长内容分块返回）
