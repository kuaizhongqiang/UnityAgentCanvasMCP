# AgentCanvas 系统总览

> 状态：🧠 概念阶段 | 更新: 2026-07-10

## 定位

Unity 作为数据仓库和 UI 模板库，Agent 通过 MCP 协议调用 CLI，从仓库选数据、套模板，自由组合输出教学内容。

## 核心原则

- Agent 输入要短，只传 ID，不生成内容
- Unity 输出可长，数据带 description 让 Agent 理解含义
- 不操作 3D，一切通过 UI 模板交互
- 搜索与取数解耦：搜索返回 ID，Unity 按 ID 返回精确内容
- 外挂架构：不迁移现有 UGUI+MVC 代码，两套系统共享数据层

## 架构

```
Agent ← MCP (stdio) → MCP Server ← HTTP/WS (3748) → Unity (EmbedIO)
                         │
                    Embedding 引擎（独立进程，LM Studio + Qwen3-0.6B）
```

## 技术选型

| 层 | 选型 |
|:--|:--|
| Unity HTTP/WS | EmbedIO |
| CLI | Python + PyInstaller → 单 .exe |
| MCP Server | Python（stdio），复用 CLI 核心 |
| Embedding | Qwen3-Embedding-0.6B，Apache 2.0，LM Studio |
| UI | UI Toolkit（UXML + USS） |

## 路径

- 源码：`AgentCanvas/CLI/`（和 Assets 同级）
- 构建：`CLI/ → PyInstaller → Assets/StreamingAssets/AgentCanvas/ → Unity Build 自动带走`
- 端口：3748，Unity 侧 `GlobalCLIMgr.cs` 管理，CLI 侧 `.env`

## 文档索引

| 文档 | 内容 |
|:--|:--|
| [Architecture](Architecture.md) | 组件关系、线程模型、GlobalCLIMgr、生命周期 |
| [Commands](Commands.md) | 20 个命令（5 类）、错误码 |
| [UI-Templates](UI-Templates.md) | 布局/元件/交互规范、页面 JSON 结构 |
| [Data-Model](Data-Model.md) | DataBase 改动、搜索数据格式、page 配置结构 |
| [Protocol](Protocol.md) | HTTP API、WebSocket 事件、回执、降级 |
| [MCP-Tools](MCP-Tools.md) | MCP 工具接口定义 |
| [Embedding](Embedding.md) | RAG 服务、模型部署、索引策略 |
| [Build-Deploy](Build-Deploy.md) | PyInstaller 打包、CI、环境配置 |
| [Security](Security.md) | 鉴权机制、token 管理、.env 配置 |
| [Testing](Testing.md) | 测试策略、Mock 方案 |
| [Debugging](Debugging.md) | 日志、调试工具、问题排查 |

## 两条底线

1. **交互反馈即时**：客观题一个 MCP 往返完成 result.show。主观题 Agent 判断后反馈。
2. **搜索是数据发现入口**：Agent 通过自然语言搜索找数据，search.data 返回 knowledgeOriginal 作为二次生成锚点。
