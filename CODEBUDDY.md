# CODEBUDDY.md

## 项目概述

AgentCanvas 是一个 MCP 工具集，让 AI Agent 通过自然语言驱动 Unity UI Toolkit，
自由组合教学数据和交互模板，输出教学内容。

## 架构

```
Agent ← MCP (stdio) → MCP Server ← HTTP/WS (3748) → Unity (EmbedIO)
                         │
                    Embedding 引擎（独立进程，LM Studio + Qwen3-Embedding-0.6B）
```

## 技术栈

| 层 | 选型 |
|:--|:--|
| Unity HTTP/WS | EmbedIO（端口 3748） |
| MCP Server | Python（stdio 协议，复用 cli_core.py） |
| CLI 调试工具 | Python + PyInstaller → cli.exe |
| Embedding | Qwen3-Embedding-0.6B，Apache 2.0，LM Studio |
| UI 渲染 | UI Toolkit（UXML + USS），Markdown 富文本 |

## 仓库关系

本仓库通过 git submodule 嵌入 MCV_Module（Unity 项目）：

```
UnityAgentCanvasMCP (本仓库) ←── submodule ──→ MCV_Module/AgentCanvas/
       │
       ├── docs/          设计文档（11 份）
       └── cli/           Python 源码
```

### 编辑边界

- **本仓库编辑**：`docs/`、`cli/` 所有文件
- **MCV_Module 编辑**：`GlobalCLIMgr.cs`（Unity C#，依赖 Unity API）
- **严禁**：将 `.cs` 文件放入本仓库，将文档修改直接写入 MCV_Module 的 submodule 副本

### 同步操作

本仓库 push 后，MCV_Module 侧执行：
```bash
cd AgentCanvas && git pull origin main && cd .. && git add AgentCanvas && git commit
```

详见 `.codebuddy/skills/agentcanvas-repos/`（MCV_Module 仓库内）。

## 关键设计决策

1. **外挂架构**：CLI+MCP 是独立模块，不迁移 MCV_Module 现有 UGUI+MVC 代码。两套系统共享 DataBase 数据层
2. **搜索与取数解耦**：`search.data` 返回 ID + knowledgeOriginal 锚点，`get.data` 按 ID 取精确内容
3. **交互反馈**：客观题 result.show 一个 MCP 往返完成，主观题 Agent 判断后反馈。interaction 回调携带 correctAnswer + explanation
4. **两条底线**：(1) 交互反馈即时 (2) search.data 是数据发现入口
5. **session 改名 dialog**：避免与 Agent 的 LLM session 混淆
6. **UI 元件评分**：增加 grading 字段（auto=客观题/agent=主观题）
7. **全量日志**：CLI 收发全量记入 logs/dialog_{id}.jsonl，可回馈 Embedding 索引

## 命令分类（5 类，19 个命令）

| 分类 | 命令 |
|:--|:--|
| 帮助 | help、docs |
| 查询 | whoami、dialog、page.list、list.templates、search.data、get.data、usage |
| 页面操作 | page.create、run、update、clear、result.show、page.delete、stop |
| 队列 | queue |
| 配置 | init、restart |

## 页面方案（5 种，Phase 1 实现 3 种）

layout + element 组合模板：knowledge_card、step_guide、quiz、compare、explore

## 项目状态

🧠 概念阶段，文档齐备，待进入实施。
