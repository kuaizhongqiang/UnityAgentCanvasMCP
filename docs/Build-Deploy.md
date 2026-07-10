# Build & Deploy 构建与部署

> 状态: 🧠 概念阶段

## 源码结构

```
项目根目录/
├── Assets/
│   ├── Scripts/
│   │   └── GlobalManager/
│   │       └── GlobalCLIMgr.cs      ← Unity 侧（新增）
│   ├── StreamingAssets/
│   │   └── AgentCanvas/              ← PyInstaller 构建输出目标
│   └── Documents/
│       └── AgentCanvas/                 ← 本文档目录
├── CLI/                             ← Python 源码
│   ├── cli_core.py                  # HTTP 封装 + 命令定义
│   ├── mcp_server.py                # MCP 协议适配
│   ├── embedding_client.py          # LM Studio 客户端
│   ├── main.py                      # 命令行入口（argparse/click）
│   ├── .env                         # 本地配置（不提交）
│   ├── .env.example                 # 配置模板
│   ├── requirements.txt
│   └── build.py                     # PyInstaller 构建脚本
```

`requirements.txt`：
```
pyinstaller>=6.0
mcp>=1.0
httpx>=0.27
websockets>=12.0
numpy>=1.26
python-dotenv>=1.0
click>=8.0
```

## CLI 构建（PyInstaller）

```bash
# 从项目根目录执行
cd CLI
python build.py
```

`build.py` 职责：
1. 调用 PyInstaller 编译 `main.py` → `../Assets/StreamingAssets/AgentCanvas/cli.exe`
2. 调用 PyInstaller 编译 `mcp_server.py` → `../Assets/StreamingAssets/AgentCanvas/mcp.exe`
3. 复制 `.env.example` 到输出目录

构建产物及运行时目录 `Assets/StreamingAssets/AgentCanvas/`：
```
cli.exe                   # 命令行工具
mcp.exe                   # MCP Server
.env.example              # 配置模板
config.json               # init 持久化配置（运行时写入 persistentDataPath，非 StreamingAssets）
logs/                     # 全量收发日志 (dialog_{id}.jsonl)
dialogs/                  # dialog 摘要 (dialog_{id}.json)
```

## Unity 构建

Unity Build 自动将 `Assets/StreamingAssets/AgentCanvas/` 打包到 `{ProjectName}_Data/StreamingAssets/AgentCanvas/`。

构建后目录：
```
Build/
├── MCV_Module.exe
└── MCV_Module_Data/
    └── StreamingAssets/
        └── AgentCanvas/
            ├── cli.exe
            ├── mcp.exe
            └── .env.example
```

用户将 `.env.example` 复制为 `.env` 并填入 token。

## CI 集成

GitHub Actions 流程：

```
1. Unity Build（现有 build.yml）
2. CLI Build（新增步骤）
   - setup-python
   - cd CLI && pip install -r requirements.txt
   - python build.py
3. 产物归档
   - Unity Build 输出（含 CLI）
   - 或单独的 CLI 制品
```

## 版本管理

- `CLI/` 目录纳入 Git，和 Unity 项目同一仓库
- `.env` 加入 `.gitignore`，不提交
- CLI 版本号跟随 Unity 项目版本号
- Embedding 模型不纳入版本控制，通过 LM Studio 独立管理

## 开发环境

```bash
# 本地开发（不用 PyInstaller，直接 python）
cd CLI
cp .env.example .env   # 编辑填入 token
python main.py help    # 测试 CLI
python mcp_server.py   # 启动 MCP Server

# LM Studio
# 下载 Qwen3-Embedding-0.6B
# 启动本地服务
```
