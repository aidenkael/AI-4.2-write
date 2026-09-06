# 02_素材知识库

与具体外部素材绑定、可追溯到来源的长期知识资产库。
当前主要资产为 BookDistill 产出的 BKP 与 MethodDistill 产出的方法知识包；每项知识保留 provenance。
原始素材不在本目录（→ 01_原始素材）；跨源、经创作验证的成熟知识在 04_写作知识库。

**本目录 = formal-only：只存放已定稿、可追溯来源、可被 KnowledgeRetrieve 发现的知识包。**
未完成 / 失败 / 取消的蒸馏输出绝不写入本目录（它们只停留在 `06_工作区` 的 request-scoped staging）。

## 放什么

- BookDistill 正式产出的 book_xxx 目录
- BKP（identity / profile / knowledge / deep_dive / work_map）
- evidence（逐章证据）
- distill_manifest / book_profile / chapters_index

## 不放什么

- 原始文件（→ 01_原始素材）
- 原创作品（→ 03_作品工程）
- 跨书通用写作知识（→ 04_写作知识库）
- 开发实验报告、临时蒸馏结果
- **未定稿 / 失败 / 取消的蒸馏中间产物**（→ `06_工作区/BookDistill|MethodDistill/<request_id>_...` staging，Local Only，不可检索）

## 蒸馏 staging → 受控发布（§9）

```text
06 Prepare 真实 Markdown
→ 06_工作区/BookDistill|MethodDistill/<request_id>_<asset>_<名称>/ 请求级 staging
→ Agent 只读 Prepare MD、只写该 staging
→ 确定性 finalize/acceptance（against staging）
→ 确认请求仍有效且未取消
→ 受控发布到 02_素材知识库/<asset>_<名称>/
→ KnowledgeRetrieve discovery 校验通过 → 才 writing-ready
```

发布是原子替换（失败不留下半成品 02 目录）；成功发布可清理 staging。已定稿包即使 06 Prepare 产物后被删除仍可用于写作（writing-callable），但重新蒸馏需要 Prepare MD 再次存在。

## BKP 与原创 Story State 的区别

| | BKP（本目录） | Story State（03_作品工程） |
|---|---|---|
| 描述对象 | 参考作品做了什么 | 原创作品当前状态 |
| Authority | 参考知识 | 原创 Canon |
| 可修改 | 蒸馏改进时更新 | 仅 author-accepted 写入 |
| 关系 | 服务创作 | 就是创作 |

**BKP 不得成为原创 Canon。**

## 已完成蒸馏

| 作品 | 目录 |
|---|---|
| 长安十二时辰 | book_0035_长安十二时辰 |
| 一九八四 | book_0038_一九八四 |
| 三体 | book_0065_三体 |

## Agent 操作规则

- 蒸馏先在 `06_工作区` staging 完成，**只有确定性 finalize/acceptance 全部通过后**才受控发布产生 `02_素材知识库/<asset>_<名称>/`；未完成/失败/取消绝不写入本目录。
- 不修改原始文件。
- BKP / 方法包更新时保持 evidence 可追溯。
- 素材类型变更后，不兼容的旧知识包不得继续可检索（由 reconcile 移入 06 recovery）。
