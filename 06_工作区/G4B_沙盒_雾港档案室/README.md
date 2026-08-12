# G4-B 一次性原创沙盒｜雾港档案室

> 用途：验证 G4 的权威工件能否脱离聊天独立恢复。**可随时丢弃，不是正式作品。**

## 读取顺序

新会话 / 新 Agent 只需依次读取：

1. `author_intent.md`
2. `story_state.yaml`
3. `briefs/brief-001.md`

不要读取旧聊天来补全故事。

## 沙盒目标

读取后三件事应该能够直接回答：

- 作者想把这篇故事写成什么体验？
- 当前已经成立的事实、人物状态和未解问题是什么？
- 下一次创作任务具体要解决什么？

若必须依赖旧聊天才能回答，G4-B 不通过。

## 边界

- 当前没有正文，因此 `accepted_text` authority 尚未出现；
- 当前 Story State 只来自本沙盒初始化时的 `manual_import:sandbox_seed_v1`；
- BKP 不进入 Story State；
- 本阶段不运行 KnowledgeRetrieve / Context Compiler；
- 不生成 Decision / State Diff；
- `contexts / decisions / diffs` 等运行时产物等 G4-C/D 真正需要时再创建，不为目录整齐提前造空文件。

## 一句话故事种子

在允许人们把记忆封存为法律证据的雾港，夜班档案员林昼收到一份以已故姐姐身份签署、却标注在姐姐死后半年提交的封存记忆。