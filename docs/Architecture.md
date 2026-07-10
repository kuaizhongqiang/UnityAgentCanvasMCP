# Architecture 架构设计

> 状态: 🧠 概念阶段

## 组件关系

```
┌─────────┐   MCP (stdio)   ┌─────────────┐   HTTP/WS   ┌──────────────┐
│  Agent  │ ←──────────────→ │  MCP Server │ ←─────────→ │   Unity      │
│ (LLM)   │                  │  (Python)   │   :3748     │  (EmbedIO)   │
└─────────┘                  └──────┬──────┘             └──────┬───────┘
                                    │                           │
                              LM Studio              GlobalCLIMgr.cs
                              (Embedding)              (主线程调度)
```

三层结构：
1. **Agent 层**：LLM，通过 MCP 工具调用
2. **MCP 层**：Python MCP Server（mcp_server.py / mcp.exe），命令编排 + Embedding 搜索 + 回执匹配 + 重试
3. **Unity 层**：GlobalCLIMgr 管理 HTTP/WS 服务，主线程调度执行

> `cli.exe`（main.py 编译）是开发调试工具，`mcp.exe`（mcp_server.py 编译）是生产环境 MCP Server。Unity 启动 mcp.exe，开发者手动调试用 cli.exe。

## 线程模型

```
网络线程（EmbedIO）      主线程（Unity）
     │                      │
     │  HTTP 请求            │
     │ ───────────────→     │
     │                      │ GlobalCLIMgr.OnCommand()
     │                      │ Debug.Log / Update / Coroutine
     │ ←───────────────     │
     │  HTTP 200 (received)  │
     │                      │ ... 执行命令 ...
     │                      │ 完成后：
     │  WS completed 推送    │
     │ ←───────────────     │
```

- EmbedIO 运行在独立后台线程
- 收到 HTTP 请求后通过 `MainThreadDispatcher` 投递到 Unity 主线程（`MainThreadDispatcher` 由 GlobalCLIMgr 内部实现，与 GlobalCLIMgr 同文件）
- WebSocket 推送同样从主线程发起，EmbedIO 线程发送

## GlobalCLIMgr

```csharp
// 位置：Assets/Scripts/GlobalManager/GlobalCLIMgr.cs
// 继承 SingletonGlobalMgr<GlobalCLIMgr>

public class GlobalCLIMgr : SingletonGlobalMgr<GlobalCLIMgr>
{
    // Inspector 配置
    [SerializeField] private int port = 3748;
    [SerializeField] private string token = "";

    // EmbedIO 服务器实例
    private WebServer server;

    protected override IEnumerator DelayInit()
    {
        // 1. 读取 SystemData 中的 CLI 配置（cliEnabled, cliPort 等）
        // 2. 启动 MCP Server 进程（mcp.exe，从 Application.streamingAssetsPath + "/CLI/"）
        // 3. 启动 EmbedIO
        // 4. 注册 HTTP 路由
        // 5. 注册 WebSocket 模块
        yield break;
    }
```

SystemData 新增字段：

| 字段 | 类型 | 默认值 | 说明 |
|:--|:--|:--|:--|
| `cliEnabled` | bool | true | CLI 功能总开关 |
| `cliAutoStart` | bool | true | 是否自动启动 CLI 进程 |
| `cliPort` | int | 3748 | HTTP/WS 端口 |

配置优先级：Inspector > `.env` > SystemData 默认值。运行时 token 以 Inspector 为准（安全性由 localhost 隔离兜底）。

```csharp
    // HTTP 端点
    // POST /cmd — 命令入口（command + params 在 JSON body 中）
    // GET /ws — WebSocket 升级

    // CLI 进程管理
    private void StartCLIProcess()
    {
        // Process.Start("mcp.exe") 从 Application.streamingAssetsPath + "/CLI/"
    }
    private void StopCLIProcess()
    {
        // Process.Kill(mcp.exe) 或优雅退出
    }

    // Agent 状态（显示在 Inspector 或 UI 角标）
    public string AgentStatus { get; private set; } // "idle" | "thinking" | "searching" | "rendering"

    // 内部
    private void ExecuteCommand(string type, JObject payload, string requestId)
    {
        // 1. 鉴权检查
        // 2. 主线程调度
        // 3. 回调结果
    }
}
```

## 生命周期

```
Unity 启动
  → Setup.cs 初始化 GlobalCLIMgr
    → DelayInit() 启动 mcp.exe（Process.Start）
      → 启动 EmbedIO
        → HTTP 端点就绪
          → Agent 可连接

Unity 退出
  → GlobalCLIMgr.OnDestroy()
    → 关闭 CLI 进程（Process.Kill / 优雅退出）
      → EmbedIO.Stop()
        → WebSocket 断开所有连接
```

CLI 进程与 Unity 生命周期同步：Unity 启动则 CLI 启动，Unity 退出则 CLI 退出。

## 外挂原则

- 现有 MCV_Module（UGUI + MVC）代码不动
- GlobalCLIMgr 注册到 Setup.cs 初始化流程（新增第 10 个 GlobalManager）
- UI Toolkit 页面在独立的 UIDocument 上渲染，与现有 Canvas 平行
- 共享数据层：DataBase.description 是唯一改动

> 与现有 `unity-mcp` 包的关系：项目 Library 中存在 `com.coplaydev.unity-mcp`，该包是 Editor 工具。AgentCanvas 的 MCP Server（Python 侧）是独立运行时方案，通过 HTTP/WS 直连 Unity，不依赖该包。
