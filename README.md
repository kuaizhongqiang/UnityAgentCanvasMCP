# AgentCanvas

> AI Agent 通过 MCP 驱动 Unity UI Toolkit，自由组合教学内容和交互。

## 是什么

AgentCanvas 是一套 MCP 工具集 + 文档规范，让 AI Agent 通过自然语言搜索数据、选择模板、组合页面、驱动 Unity 实时渲染教学内容。

Agent 是指挥者，Unity 是画布（Canvas），MCP 是画笔协议。

## 怎么工作

```
Agent ← MCP (stdio) → MCP Server ← HTTP/WS (3748) → Unity (EmbedIO)
                         │
                    Embedding 引擎（LM Studio + Qwen3-0.6B）
```

1. Agent 调 `search.data "显微镜"` → 搜索相关知识数据
2. Agent 选页面方案 → `page.create` + 绑定数据 + `run`
3. 学生在 Unity 中看到渲染的教学页面
4. 学生答题 → WebSocket 回调 → Agent 判题 → `result.show` 原地反馈

## 文档

[完整设计文档](docs/README.md)，11 份文档覆盖架构、命令、协议、UI 模板、Embedding 等。

## 仓库关系

本仓库通过 git submodule 嵌入 [MCV_Module](https://github.com/kuaizhongqiang/MCV_Module)（Unity 虚拟仿真项目）。

| 内容 | 编辑在哪 |
|:--|:--|
| 设计文档、Python CLI 源码 | **本仓库** |
| GlobalCLIMgr.cs（Unity C#） | MCV_Module |
| 运行时 .exe 产物 | 本仓库 GitHub Releases → MCV_Module 构建时拉取 |

## 技术栈

| 层 | 选型 |
|:--|:--|
| Unity HTTP/WS | EmbedIO |
| MCP Server | Python（stdio） |
| CLI 调试工具 | Python + PyInstaller |
| Embedding | Qwen3-Embedding-0.6B，Apache 2.0，LM Studio |
| UI | UI Toolkit（UXML + USS） |

## 状态

🧠 概念阶段，文档齐备，待进入实施。
