# Debugging 调试与日志

> 状态: 🧠 概念阶段

## 日志级别

| 级别 | 用途 |
|:--|:--|
| DEBUG | 命令详细参数、WS 消息体 |
| INFO | 命令开始/结束、连接建立/断开 |
| WARNING | 重试、降级、超时 |
| ERROR | 鉴权失败、命令执行异常 |

## 日志输出

- **Python 侧**：stdout（开发）+ 文件（生产）。开发时 `./CLI/logs/`，构建后 `StreamingAssets/CLI/logs/`。通过 `LOG_LEVEL` 和 `LOG_FILE` 配置
- **Unity 侧**：`Debug.Log` + 可选文件输出

## 关键日志点

| 组件 | 日志点 |
|:--|:--|
| MCP Server | 启动、Agent 连接/断开、工具调用开始/结束/耗时 |
| CLI | 每条命令的 requestId、received 和 completed 时间戳 |
| Unity | HTTP 请求接收、鉴权结果、命令执行开始/结束 |
| Embedding | LM Studio 连接状态、查询耗时、匹配分数 |

## 调试工具

### 手动测试命令
```bash
# 直连 Unity（不通过 MCP）
python main.py help
python main.py get.data equipment_03
python main.py list.templates
```

### WebSocket 消息查看
```bash
# 用 wscat 监控 WS 消息流
wscat -c ws://localhost:3748/ws?token=xxx
```

### Unity 侧
- Inspector 中 GlobalCLIMgr 显示当前连接数、最后命令、命令队列长度
- Editor 模式下 Log 窗口实时查看 HTTP/WS 消息

## 常见问题排查

| 问题 | 排查路径 |
|:--|:--|
| 端口被占用 | 检查是否有残留 CLI/Unity 进程，`netstat -ano \| findstr 3748` |
| 鉴权失败 401 | 检查 `.env` 中 `CLI_TOKEN` 与 Unity Inspector 中 token 是否一致 |
| MCP Server 启动失败 | 检查 `StreamingAssets/CLI/mcp.exe` 是否存在，Python 环境是否正确 |
| search.data 返回空 | 检查 LM Studio 是否启动、模型是否加载、数据是否已构建索引 |
| WS 频繁断开 | 检查防火墙设置、网络稳定性、命令执行是否超时 |
