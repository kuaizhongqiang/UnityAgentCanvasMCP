# Testing 测试策略

> 状态: 🧠 概念阶段

## 测试层次

```
E2E: Agent → MCP Server（mcp.exe）→ Unity HTTP/WS（生产链路）
  ↑
CI Debug: 开发者 → cli.exe → Unity HTTP（手动调试）
  ↑
Integration: MCP Server ↔ Unity HTTP/WS（组件通信）
  ↑
Unit: Python cli_core / Unity GlobalCLIMgr（函数级）
```

## 单元测试

**Python 侧**（pytest）：
- `cli_core.py` 命令路由和参数解析
- `embedding_client.py` LM Studio API 调用逻辑
- requestId 生成和匹配逻辑

**Unity 侧**（Unity Test Framework，Edit Mode）：
- `GlobalCLIMgr` token 鉴权逻辑
- 命令 JSON 解析和路由
- 错误码返回

## 集成测试

- MCP Server ↔ Unity HTTP/WS 通信握手
- 完整命令流程：received → completed 回执匹配
- WebSocket 断开重连
- 批量命令队列执行

## E2E 测试

- 模拟 Agent 调用完整 MCP 工具链路
- 页面创建 → 搜索数据 → 绑定 → 执行 → 清空
- 多 dialog 隔离

## Mock 策略

**无 LM Studio 时**：`search.data` 降级为关键词匹配，用本地 fixture 数据测试。

**无 Unity 时**：Python 侧用 HTTP mock server 模拟 Unity 的 `/cmd` 端点和 WS 回执。

## 后续细化

- 测试覆盖率目标
- CI 中的测试步骤（GitHub Actions）
- 测试数据 fixture 设计
