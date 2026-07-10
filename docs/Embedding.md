# Embedding / RAG 服务

> 状态: 🧠 概念阶段

## 定位

独立语义搜索服务，自然语言 → 数据 ID。不在 Unity 内跑模型。

## 架构

```
Agent → MCP Server → Embedding 引擎（LM Studio）
              │
         search.data 返回 Top-N ID + knowledgeOriginal
              │
         get.data 到 Unity 取精确内容
```

搜索与取数解耦：Embedding 只返回 ID，Unity 根据 ID 返回精确内容（地面真值）。

## 模型

**优选**：`Qwen/Qwen3-Embedding-0.6B`

| 属性 | 值 |
|:--|:--|
| 参数 | 0.6B |
| 显存（FP16） | ~1.2GB |
| 许可证 | Apache 2.0（商业宽松） |
| 中文 | 原生支持 |
| 下载量 | 11M+（HuggingFace） |

**备选**：Qwen3-Embedding-4B（~8GB 显存，精度更高）。

## 推理引擎

LM Studio（端点可配置，HTTP API 调用）：

```
LM Studio → 加载 Qwen3-Embedding-0.6B → 暴露 localhost:1234
MCP Server → POST /v1/embeddings → 获取向量
```

模型文件不随 Unity 打包。LM Studio 环境下独立部署和升级。

## 约束

| 约束 | 要求 |
|:--|:--|
| 开源协议 | MIT / Apache 2.0，商业应用宽松 |
| 显存 | ≤12GB |
| 推理引擎 | LM Studio，端点可配置 |
| 中文 | 必须原生支持中文 embedding |

## 索引策略

方向：
- **运行时首次构建**：MCP Server 启动时检查索引文件。若不存在，读取 Unity 导出的 `data_export.json` 逐条计算 embedding，生成索引文件并缓存
- 数据量 < 1000 条时首次构建耗时 < 5 秒（Qwen3-0.6B），后续启动直接加载缓存

> 索引文件位于 `StreamingAssets/AgentCanvas/index/`，与 `data_export.json` 同目录。

## 数据准备

需要参与 embedding 的数据：

1. 所有 DataBase 子类的 `id + displayName + description`
2. 每个数据关联的 `knowledgeOriginal` 原文
3. `tag` 标签数组

索引构建时拼接为单个文本进行 embedding：

```
"{id} {displayName} {description} {tags} {knowledgeOriginal}"
```

## 搜索流程

```
1. Agent 传自然语言 query
2. MCP Server 调用 LM Studio 获取 query embedding
3. 与预建索引做余弦相似度计算
4. 返回 Top-N（默认 5 条）
5. 每条含：id、desc、tag、data、knowledgeOriginal、score、templateType（格式定义见 [Data-Model](Data-Model.md)，命令见 [Commands](Commands.md)）
```

Agent 根据 knowledgeOriginal 锚点判断哪条最合适，再用 get.data 取完整数据。
