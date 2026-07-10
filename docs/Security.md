# Security 鉴权与安全

> 状态: 🧠 概念阶段

## 鉴权模型

简单共享密钥。Unity 侧存储 token，CLI 请求携带 token，Unity 比对通过即放行。

## token 配置

### Unity 侧

`GlobalCLIMgr.cs`：
```csharp
[SerializeField] private string token = "";
```

Inspector 中手动填入或在构建前脚本注入。token 编译进 Unity 包内。

### CLI 侧

`.env` 完整内容：
```
# Unity 连接
CLI_PORT=3748
CLI_TOKEN=your_secret_token

# Embedding 引擎
LM_STUDIO_HOST=localhost
LM_STUDIO_PORT=1234
EMBEDDING_MODEL=Qwen3-Embedding-0.6B

# 知识文档路径
KNOWLEDGE_PATH=./knowledge_docs/

# 搜索
TOP_N=5

# 超时（秒）
HTTP_TIMEOUT=5
COMMAND_TIMEOUT=30

# 日志
LOG_LEVEL=INFO
```

`.env.example` 随构建分发，用户填入自己的配置。

## 传输方式

HTTP 请求带 `Authorization` header：
```
Authorization: Bearer {token}
```

WebSocket 连接时 URL 参数带 token：
```
ws://localhost:3748/ws?token=your_secret_token
```

Unity GlobalCLIMgr 在每个入口处比对。不匹配返回 401。

> 环境变量 `CLI_TOKEN` 映射为请求中的 `{token}`。

## 安全边界

- 仅监听 `localhost`，不对外暴露
- 无用户注册/登录体系，不涉及隐私数据
- token 不通过网络传输（本地 localhost），无中间人风险
- 不存储学生操作数据，仅实时推送事件给 Agent

## 风险说明

| 风险 | 说明 | 缓解 |
|:--|:--|:--|
| token 泄露 | .env 文件被复制传播 | 仅本地使用，不出 localhost |
| Unity Inspector 暴露 | token 在 Inspector 可见 | 构建前脚本注入，不在 Inspector 持久化 |
| 重放攻击 | 同一 token 无限复用 | localhost 限定，无外部攻击面 |

## 待评估

- 是否需要 token 轮换机制
- MCP Server 连接 Unity 时是否需要独立鉴权（相对于 CLI 直连）
