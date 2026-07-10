# Commands 命令定义

> 状态: 🧠 概念阶段

## 命令格式

所有命令通过 HTTP POST 发送，params 结构依命令而异：

```
# get.data
POST /cmd { "command": "get.data", "params": {"dataId": "equipment_03"}, "requestId": "xxx" }

# search.data
POST /cmd { "command": "search.data", "params": {"query": "显微镜"}, "requestId": "xxx" }

# result.show
POST /cmd { "command": "result.show", "params": {
    "pageId": "page_1", "dialogId": "dialog_1", "elementId": "elem_3",
    "result": { "isCorrect": true, "correctAnswer": "B", "explanation": "...", "userAnswer": "B" }
}, "requestId": "xxx" }
```

响应：
```json
{ "requestId": "xxx", "status": "received" }
```

完成后 WebSocket 推送：
```json
{ "requestId": "xxx", "status": "completed", "data": {...} }
```

总计 20 个命令（含变体），分为 5 类。

## 帮助类

### help
获取所有可用命令和用法。Agent 接入第一步必发。

### docs
列出所有可用文档清单。返回：`[{title, summary}]`。

### docs {name}
获取指定 CLI 框架文档全文。

## 查询类

### whoami
返回当前 Agent 身份信息和权限级别。

### dialog
列出所有对话。返回：`[{dialogId, status, createdAt, pageCount}]`。状态：`active` | `idle` | `closed`。每个 dialog 独立持有自己的 page 列表。

### dialog {dialogId}
获取指定对话详情。

### list.templates
列出所有 UI 模板，返回：`[{templateId, displayName}]`。

### search.data {query}
语义搜索数据。由 Embedding 引擎处理（Unity HTTP /data/export + KNOWLEDGE_PATH 文档合并索引）。返回 Top-N（含 knowledgeOriginal 锚点）。

### get.data {dataId}
按 ID 精准取数据全文（地面真值）。

### usage
获取使用统计：调用次数、对话时长等。

### status.list {dialogId}
查询指定 dialog 的所有请求状态。WS 重连后 MCP Server 调用此命令恢复状态。

返回：`[{requestId, command, status, data?}]`，status 为 `pending` | `completed` | `failed`。

## 页面操作类

### page.create {dialogId}
在指定 dialog 中新建页面。Unity 自动生成 pageId 并返回 `{pageId, dialogId}`。创建时为空白状态，初始布局使用 init 配置中的 `defaultLayout`。

### page.list {dialogId}
列出指定 dialog 下所有页面及其状态。

### run {pageId} {dialogId} [{filePath}]
执行页面配置渲染到 Unity UI。filePath 可选，传入时从 JSON 文件加载页面配置（路径相对于 `Application.streamingAssetsPath`），不传时使用已有页面配置。

### update {pageId} {dialogId} {patch}
增量修改页面，JSON Merge Patch（RFC 7396）格式。

### clear {pageId} {dialogId} [scope]
清空页面内容，可选带范围参数。

### result.show {pageId} {dialogId} {elementId} {result}
原地展示答题反馈。客观题由 interaction 回调直接触发，主观题由 Agent 判断后调用。

### page.delete {pageId} {dialogId}
删除页面及其配置。

### stop
停止当前正在执行的所有任务：取消当前运行命令 + 清空命令队列 + 停止页面渲染。

## 队列类

### queue
查看命令队列，返回排队中的命令列表。

### queue {commands}
提交批量命令，入参：命令数组，按序执行。数组元素结构：`[{command, params}]`。

### queue {commandId}
查看队列中指定命令状态：queued / running / completed / failed。

## 配置类

### init {config}
持久化到 `{persistentDataPath}/AgentCanvas/config.json`，重启/换 dialog 保留。

### restart
CLI + MCP Server 生命周期重启。清空所有状态（pages、dialogs、命令队列），init 配置保留。Unity 侧 GlobalCLIMgr 不受影响。

## 页面配置 JSON 结构

```json
{
  "pageId": "page_1",
  "dialogId": "dialog_1",
  "version": 1,
  "layout": "free_stack | waterfall | three_column",
  "elements": [
    {
      "id": "elem_1",
      "type": "title | subtitle_text | image | image_text | choice | fill | model | video | button | button_list",
      "bind": "数据ID",
      "callback": true | false,
      "grading": "auto | agent",
      "region": "left | center | right",
      "x": 0,
      "y": 0
    }
  ]
}
```

- `version`: Unity 自动自增，Agent 不管理。冲突时返回 409 Conflict
- `x`, `y`: 仅 `free_stack` 布局使用，其他布局忽略。可选，默认 (0, 0)
- `grading`: 仅 `callback: true` 时有效，缺省 = `auto`

## 错误码

| 码 | 含义 |
|:--|:--|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | 鉴权失败 |
| 404 | 页面/数据/模板不存在 |
| 409 | 版本冲突（version 不匹配） |
| 500 | 执行错误 |
| 503 | 服务未就绪 |
