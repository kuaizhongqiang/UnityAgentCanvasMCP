# Data Model 数据模型

> 状态: 🧠 概念阶段

## DataBase 改动

唯一改动：增加 `description` 字段。如加 `abstract` 需排查项目中的 `new DataBase()` 调用。

```csharp
// 位置：Assets/Scripts/Data/DataBase.cs
[Serializable]
public abstract class DataBase
{
    public string id;
    public string displayName;
    public string description;  // ← 新增
}
```

所有继承 DataBase 的数据类自动获得描述能力。CLI 通过 `get.data {id}` 返回完整字段，Agent 据此理解数据含义。

## 搜索返回格式

`search.data {自然语言}` 返回 Top-N：

```json
[
  {
    "id": "equipment_03",
    "desc": "光学显微镜构造与成像原理",
    "tag": ["显微镜", "光学", "成像"],
    "data": {
      "imagePath": "textures/microscope.png",
      "modelId": "model_microscope_01"
    },
    "knowledgeOriginal": "显微镜由目镜、物镜、载物台、聚光镜和光源组成。光线经过聚光镜照射标本...",
    "score": 0.92,
    "templateType": "image_text"
  }
]
```

| 字段 | 说明 |
|:--|:--|
| `id` | 数据唯一标识 |
| `desc` | 数据描述 |
| `tag` | 标签/关键词数组 |
| `data` | 数据内容字段 |
| `knowledgeOriginal` | 原文摘录，Agent 二次生成的锚点 |
| `score` | Embedding 相关性分数，详见 [Embedding](Embedding.md) |
| `templateType` | 建议适配的模板类型 |

## 页面配置结构

```json
{
  "pageId": "page_1",
  "version": 1,
  "layout": "three_column",
  "elements": [
    {
      "id": "elem_1",
      "type": "subtitle_text",
      "bind": "principle_01",
      "callback": false,
      "region": "left"
    },
    {
      "id": "elem_2",
      "type": "image",
      "bind": "equipment_03",
      "callback": false,
      "region": "center"
    },
    {
      "id": "elem_3",
      "type": "choice",
      "bind": "question_07",
      "callback": true,
      "region": "right"
    }
  ]
}
```

Agent 通过 `update {pageId} {patch}` 可以只修改某个 element 而不重发整页。

## 持久化配置（init）

```json
{
  "agent": {
    "name": "physics_tutor",
    "role": "assistant"
  },
  "preferences": {
    "defaultLayout": "three_column",
    "favoriteTemplates": ["subtitle_text", "choice", "image_text"],
    "dataPool": ["physics_circuit"],
    "teachingStyle": "incremental"
  }
}
```

存储在 `{persistentDataPath}/CLI/config.json`，重启后仍然有效。
