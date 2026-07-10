# CLI Python 源码 - Code Review

| Field | Value |
|:--|:--|
| Date | 2026-07-10 |
| Version | 1 |
| Reviewer | PM Review |
| Scope | CLI/*.py（7 核心文件 + 8 测试文件）、docs/Commands.md 对照 |

## Critical

### [Critical] `embedding_client.py` — `_load_data_export` 存在不可达代码（Dead Code）

- **Location**: `CLI/embedding_client.py:179-185`
- **Problem**: `return data` 在第 181 行提前返回，导致 182-185 行的数据解包逻辑（处理 `{"items": [...]}` 包装格式）永远无法执行。这意味着如果 Unity 导出的 `data_export.json` 使用对象包装格式，数据将不会被正确解析。
- **Suggestion**: 将 `return data` 移到文件末尾，让解包逻辑能正常执行：

```python
def _load_data_export(self) -> List[Dict[str, Any]]:
    path = self._data_export_path()
    if not path.exists():
        logger.warning("Data export not found at %s", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    # May be wrapped in an object
    return data.get("items", data.get("data", []))
```

---

### [Critical] `embedding_client.py` — 重复导入语句

- **Location**: `CLI/embedding_client.py:34-35`
- **Problem**: `KnowledgeDoc` 和 `KnowledgeReader` 从 `knowledge_reader` 导入了两次：第 34 行和第 35 行完全相同。
- **Suggestion**: 删除重复的第 35 行。

---

### [Critical] `embedding_client.py` — 嵌入矩阵索引映射错误

- **Location**: `CLI/embedding_client.py:291-300, 407-411`
- **Problem**: `_build_embeddings_matrix()` 只收集有 embedding 的 `IndexEntry` 构建矩阵（跳过 `embedding=None` 的条目）。但在 `search()` 中，`np.argsort(scores)` 返回的索引是矩阵中的位置，直接用这个索引访问 `self._index` 会导致**索引错位**。例如：`_index = [A(有embedding), B(无embedding), C(有embedding)]`，矩阵为 `[vec_A, vec_C]`，如果 C 的相似度最高 → argsort 返回 `[1, 0]` → 访问 `_index[1]` 得到 B 而非 C。
- **Suggestion**: 在 `_build_embeddings_matrix()` 中同时构建从矩阵索引到 `_index` 的映射表：

```python
self._embedding_map: List[int] = []  # 矩阵索引 → _index 索引
for i, entry in enumerate(self._index):
    if entry.embedding is not None:
        vectors.append(entry.embedding)
        self._embedding_map.append(i)
```

然后在 `search()` 中用 `self._embedding_map[idx]` 来取正确的条目。

---

### [Critical] `Commands.md` 定义 `status.list` 但代码未实现

- **Location**: `docs/Commands.md:69-72` vs `CLI/cli_core.py`, `CLI/mcp_server.py`
- **Problem**: 设计文档明确描述了 WS 重连后通过 `status.list {dialogId}` 恢复状态的机制，但 `COMMAND_DEFINITIONS` 中没有此命令，`mcp_server.py` 中也没有对应的 MCP 工具。这导致 WS 重连后的状态恢复功能不完整 —— 当前分支 `phase3-logging-reconnect` 的核心功能缺失。
- **Suggestion**: 在 `COMMAND_DEFINITIONS` 中添加 `status.list` 命令定义，并在 `mcp_server.py` 中实现对应的 MCP 工具。

---

## Major

### [Major] 文档与代码命令参数不一致 — 多处缺失 `dialogId`

- **Location**: `docs/Commands.md` vs `CLI/cli_core.py:120-225`
- **Problem**: `Commands.md` 描述的命令签名包含 `dialogId` 参数（如 `page.create {dialogId}`, `run {pageId} {dialogId}`, `result.show {pageId} {dialogId} {elementId} {result}` 等），但 `COMMAND_DEFINITIONS` 中所有 page 相关命令均未定义 `dialogId` 参数。当前代码的 page 操作是全局的，没有 dialog 隔离。这导致：
  - 多对话场景下 page 管理混乱
  - Agent 无法在指定 dialog 中创建/操作 page
- **Suggestion**: 
  1. 如果 dialog 隔离是计划中的 Phase 4 功能，请在 `Commands.md` 中标注为 "待实现"。
  2. 如果应立即实现，为所有 page 命令添加 `dialogId` 参数。
  3. 无论如何，确保文档与代码同步。

---

### [Major] `mcp_server.py` — MCP 工具参数名与内部函数参数名不一致

- **Location**: `CLI/mcp_server.py`
- **Problem**: 多处 MCP 工具参数名与对应内部方法参数名不匹配，依赖 Python 的位置传参。如果将来参数顺序变动或 FastMCP 框架变更，会导致静默错误：

| MCP 工具参数 | 内部方法参数 | 行号 |
|:--|:--|:--|
| `result` | `result_json` | 494, 240 |
| `commands` | `commands_json` | 523, 286 |
| `config` | `config_json` | 538, 315 |
| `patch` | `patch`（类型不匹配） | 480, 214 |

- **Suggestion**: 统一参数名。建议内部方法参数名与 MCP 工具参数名保持一致。

---

### [Major] `dialog_logger.py` — `write_summary` 的 `startedAt` 不准确

- **Location**: `CLI/dialog_logger.py:219`
- **Problem**: `write_summary()` 使用 `self._timestamp()` 写入 `startedAt` 字段，该值反映的是 summary 写入时的 UTC 时间，而非 dialog 实际开始的时间。`_start_time` 在 `__init__` 中已正确记录（`time.time()`），但未用于 `startedAt`。
- **Suggestion**: 将 `startedAt` 改为在 `__init__` 中记录的 ISO 时间戳：

```python
self._started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
```
然后在 `write_summary` 中使用 `"startedAt": self._started_at`。

---

### [Major] `build.py` — `PYINSTALLER_OPTS` 中的 `--noconsole` 被覆盖

- **Location**: `CLI/build.py:56-61` vs `CLI/build.py:121-133`
- **Problem**: `PYINSTALLER_OPTS` 常量定义了 `--noconsole`，但 `build_exe()` 函数在 121-122 行通过 `console` 参数动态控制 `--noconsole` 的添加。`PYINSTALLER_OPTS` 中的 `--noconsole` 虽然未被实际使用（因为 opts 是重建的），但它表明意图不清晰，容易导致混淆。
- **Suggestion**: 从 `PYINSTALLER_OPTS` 中移除 `--noconsole`，完全由 `console` 参数控制。

---

## Minor

### [Minor] `embedding_client.py` — pickle 反序列化安全风险

- **Location**: `CLI/embedding_client.py:326-327`
- **Problem**: 使用 `pickle.load(f)` 加载缓存的嵌入索引。pickle 在加载时可能执行任意代码，存在反序列化攻击风险。虽然当前场景是本地信任数据，但作为安全实践应当避免。
- **Suggestion**: 改用 JSON 序列化（numpy 数组转 list）存储嵌入索引，避免 pickle 安全风险。如果必须用 pickle，至少添加数据完整性校验。

---

### [Minor] `mcp_server.py` 和 `main.py` — 重复的 `setup_logging` 函数

- **Location**: `CLI/mcp_server.py:39-44`, `CLI/main.py:41-46`
- **Problem**: 两个文件各自定义了功能完全相同的 `setup_logging` 函数。
- **Suggestion**: 将 `setup_logging` 提取到 `cli_core.py` 或新建 `logging_setup.py` 作为共享工具函数。

---

### [Minor] `main.py` — `async_cmd` 有未解决的类型警告

- **Location**: `CLI/main.py:92-96`
- **Problem**: `type: ignore[return]` 注释表明装饰器的类型签名有已知问题未解决。`click.pass_context` 包裹的 lambda 不匹配 Click 期望的类型。
- **Suggestion**: 重构 `async_cmd` 为标准的 Click 装饰器工厂模式，或使用 `click.decorators` 的 `make_pass_decorator` 模式。

---

### [Minor] `knowledge_reader.py` — frontmatter 解析器使用简单 KV 模式而非标准 YAML

- **Location**: `CLI/knowledge_reader.py:66-103`
- **Problem**: `_parse_frontmatter` 是自己实现的行级 key:value 解析器，不支持嵌套结构、多行值、布尔值、数字等 YAML 特性。代码注释说 "For full YAML, use the 'yaml' package"，但实际未实现。
- **Suggestion**: 添加可选的 `yaml` 包依赖：如果 `yaml` 可用则使用 `yaml.safe_load()`，否则回退到当前的简化解析器。

---

### [Minor] `dialog_logger.py` — 文件名与文档路径不一致

- **Location**: `CLI/dialog_logger.py:8` vs `CLI/dialog_logger.py:66-74` vs `CODEBUDDY.md`
- **Problem**: 文件注释说日志输出到 `logs/dialog_{id}.jsonl`，但构造函数默认 `base = Path.cwd()` 使得在生产环境（由 Unity 启动）和开发环境的工作目录可能不一致。
- **Suggestion**: 确认日志路径是否与 `streaming_assets_path` 正确关联，增加路径断言或文档说明。

---

## Suggestions

### [Suggestion] 缺少 `mcp_server.py` 的单元测试

- **Location**: `CLI/tests/`
- **Problem**: 测试套件覆盖了 `cli_core.py`, `dialog_logger.py`, `embedding_client.py`, `knowledge_reader.py` 和 E2E 场景，但 `mcp_server.py`（生产环境入口）没有专门的单元测试。FastMCP 的 startup/shutdown 生命周期、工具注册、参数解析等逻辑未被测试。
- **Suggestion**: 为 `AgentCanvasMCPServer` 类添加单元测试，至少覆盖：
  - `_exec` 的锁机制
  - JSON 解析错误处理（`tool_update`, `tool_result_show`, `tool_queue_push`, `tool_init`）
  - startup/shutdown 生命周期

---

### [Suggestion] `tool_run` 和 `tool_run_file` 功能重复

- **Location**: `CLI/mcp_server.py:201-212`
- **Problem**: `tool_run_file` 和 `tool_run` 都执行 `run` 命令，唯一的区别是 `tool_run` 的 `file_path` 可选而 `tool_run_file` 的 `filePath` 必需。两个工具的功能完全重叠。
- **Suggestion**: 移除 `tool_run_file`，只保留 `tool_run`（已有可选 `filePath` 参数），减少 MCP 工具列表的冗余。

---

### [Suggestion] 统一错误响应格式

- **Location**: 多文件
- **Problem**: `UnityClient.send_command()` 构造错误响应时（如 HTTP 超时、连接失败）手动构建 dict；而 `UnityClient.execute()` 做参数校验时也构建不同格式的错误 dict；`mcp_server.py` 中各工具函数也有自己的错误格式。错误码 408 在 `send_command`（HTTP 超时）和 `wait_for_receipt`（WS 超时）两处重复定义。
- **Suggestion**: 创建统一的 `ErrorResponse` 工厂函数，确保所有错误响应遵循相同格式。

---

### [Suggestion] mock_unity_server 的 `log_message` 覆盖可能导致调试困难

- **Location**: `CLI/tests/mock_unity_server.py:320-321`
- **Problem**: HTTP handler 覆盖了 `log_message` 方法改为 `logger.debug`，但只打印格式化的消息。如果需要排查 HTTP 请求体或状态码细节，当前日志级别不够。
- **Suggestion**: 在 debug 模式下保留更多 HTTP 上下文（请求路径、状态码、body 长度等）。

---

### [Suggestion] E2E 测试中的 WS 连接补丁代码大量重复

- **Location**: `CLI/tests/test_e2e.py:111-121, 158-168, 198-206`
- **Problem**: `patched_connect()` 在 3 个测试中重复定义，代码完全相同。
- **Suggestion**: 将 `patched_connect` 提取为 conftest.py 中的 fixture 或工具函数。

---

## 文档与代码一致性对照

| 命令 | `Commands.md` 签名 | `COMMAND_DEFINITIONS` 实际 | 状态 |
|:--|:--|:--|:--|
| `help` | `help` | `help {}` | ✅ |
| `docs` | `docs` | `docs {}` | ✅ |
| `docs_get` | `docs {name}` | `docs_get {name}` | ✅ |
| `whoami` | `whoami` | `whoami {}` | ✅ |
| `dialog` | `dialog` / `dialog {dialogId}` | `dialog {dialogId?}` | ✅ |
| `list.templates` | `list.templates` | `list.templates {}` | ✅ |
| `search.data` | `search.data {query}` | `search.data {query}` | ✅ |
| `get.data` | `get.data {dataId}` | `get.data {dataId}` | ✅ |
| `usage` | `usage` | `usage {}` | ✅ |
| `status.list` | `status.list {dialogId}` | **缺失** | ❌ |
| `page.create` | `page.create {dialogId}` | `page.create {pageId}` (无 dialogId) | ⚠️ |
| `page.list` | `page.list {dialogId}` | `page.list {}` (无 dialogId) | ⚠️ |
| `run` | `run {pageId} {dialogId} [{filePath}]` | `run {pageId} [{filePath}]` (无 dialogId) | ⚠️ |
| `update` | `update {pageId} {dialogId} {patch}` | `update {pageId} {patch}` (无 dialogId) | ⚠️ |
| `clear` | `clear {pageId} {dialogId} [scope]` | `clear {pageId} [scope]` (无 dialogId) | ⚠️ |
| `result.show` | `result.show {pageId} {dialogId} {elementId} {result}` | `result.show {pageId} {elementId} {result}` (无 dialogId) | ⚠️ |
| `page.delete` | `page.delete {pageId} {dialogId}` | `page.delete {pageId}` (无 dialogId) | ⚠️ |
| `stop` | `stop` | `stop {}` | ✅ |
| `queue` | `queue` / `queue {commands}` / `queue {commandId}` | `queue {commandId?}` + `queue.push {commands}` | ✅ |
| `init` | `init {config}` | `init {config}` | ✅ |
| `restart` | `restart` | `restart {}` | ✅ |

命令数量差异：文档声称 20 条，代码实际 21 条（多了 `queue.push` 显式命令 + `docs_get` 作为独立命令）。

---

## Summary

- **Critical**: 3
- **Major**: 4
- **Minor**: 5
- **Suggestions**: 5

### Top Priority

1. **修复 `_load_data_export` 的 Dead Code** — 数据导入功能不完整
2. **修复嵌入矩阵索引映射错误** — 语义搜索结果可能返回错误的条目
3. **实现 `status.list` 命令** — WS 重连恢复机制缺失核心功能
4. **删除重复导入** — `embedding_client.py:34-35` 重复导入
