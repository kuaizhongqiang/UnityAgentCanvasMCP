# UI Templates 模板系统

> 状态: 🧠 概念阶段 | 方案: UI Toolkit（UXML + USS）

## 设计原则

三层组合：Agent 选布局 → 往分区填元件 → 绑定交互（回调）。

模板是预置组件，Agent 不生成 UI，只引用模板 ID 和数据 ID。

## 布局模板（3 种）

### 自由堆积（free_stack）
元素按坐标摆放。Agent 在 JSON 中指定每个元件的 `x`, `y` 字段（可选，默认 0, 0）。其他布局忽略 x/y。

适用：单个知识点展示（标题上、图片中、说明下）。

### 瀑布流（waterfall）
条目自动竖向排列。Agent 给条目列表，布局引擎自动计算位置。

适用：器材清单、知识点罗列、步骤列表。

### 左中右一页（three_column）
三栏分区。Agent 指定 left / center / right 各放什么元件。

适用：图文对照（左文字/中图片/右操作区）、答题互动。

## 元件（10 种）

| 元件 | 类型标识 | 可绑定数据 | 可回调 | 评分 |
|:--|:--|:--|:--:|:--|
| 标题 | `title` | text | — | — |
| 小标题+文字 | `subtitle_text` | title + content | — | — |
| 图片 | `image` | imagePath | — | — |
| 图文 | `image_text` | imagePath + content | — | — |
| 选择题 | `choice` | question + options | ✅ | auto |
| 填空题 | `fill` | question | ✅ | agent |
| 模型展示 | `model` | modelId（TextureRenderer） | — | — |
| 播放视频 | `video` | videoPath | — | — |
| 按钮 | `button` | text | ✅ | — |
| 按钮列表 | `button_list` | items[] | ✅ | — |

> 评分：`auto` = 客观题，回调携带 correctAnswer；`agent` = 主观题，回调仅携带学生答案，Agent 判断后调 result.show。

> 数据绑定格式详见 [Data-Model](Data-Model.md)。

## 交互（回调机制）

交互是元件的属性，不是独立模板。Agent 选择元件时设置 `callback: true/false`。

### 需回调

学生提交答题/选择/点击按钮后，Unity 通过 WebSocket 推送给 Agent：

```json
{
  "requestId": "xxx",
  "event": "interaction",
  "pageId": "page_1",
  "elementId": "choice_1",
  "action": "submitted",
  "data": { "answer": "B" }
}
```

Agent 收到后决定下一步：判对错、展示解析、跳转到新页面。

### 无回调

学生看完即结束。Agent 后续通过 `run` / `update` / `clear` 主动推进。

## USS 常见错误

参考 [UnitySkillForAgent/ui-toolkit skill](https://github.com/kuaizhongqiang/UnitySkillForAgent/tree/main/.claude/skills/ui-toolkit)：

| 错误 | 正确 |
|:--|:--|
| `display: block` | 只用 flex / none |
| `text-align: center` | `-unity-text-align: middle-center` |
| `rgba(0,0,0,0.5)` | `#00000080` |
| HTML `id` 属性 | UI Toolkit 用 `name` 属性代替，选择器仍是 `#name` |
| CSS calc / var / em / rem | 不支持，手工计算 |
