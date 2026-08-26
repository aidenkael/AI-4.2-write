# 04_写作知识库

经过跨作品支持和真实创作验证后，真正值得长期复用的高成熟度写作知识。

## 与 02_素材知识库 的区别

| | 02_素材知识库 | 04_写作知识库 |
|---|---|---|
| 范围 | 单个来源（参考作品 / 方法资料） | 跨作品、跨书验证 |
| 内容 | 这个来源教了什么/做了什么 | 我们有什么经验值得长期相信 |
| 成熟度 | 蒸馏定稿即可（`source_bound`） | 需经真实创作验证（`validated`） |

## 可调用包合同（KnowledgeRetrieve 检索门）

只有满足下列合同的包才会被统一检索入口加载（`source_kind = validated_knowledge`）；
当前生产无包是合法状态——缺包不造假，测试只用临时 fixture：

```text
04_写作知识库/<package>/
├─ identity.json        # schema_version = gowrite_validated_knowledge/v1
│                       # schema_status  = FINALIZED_VALIDATED（否则不可检索）
│                       # source_kind = validated_knowledge；source_id；title；
│                       # maturity = validated；provenance（来源知识 refs / 验证 refs）
├─ validation.md        # 跨作品/真实创作验证记录（证据）
└─ knowledge/
   └─ cards.md          # 规范知识卡（V0001…，与 MethodDistill 同一卡语法）
```

命中统一身份：`selection_ref = validated_knowledge/<source_id>/<卡 id>`。
04 知识可以影响 proposal/写作/检查，但永远不能写入或覆盖项目 Canon / Story State。

## 放什么

- 经过多作品和真实创作验证的写作经验
- 跨书通用的成熟写作模式与规则
- 从 BKP 和实际创作中提炼并验证的知识

## 不放什么

- 单书分析（→ 02_素材知识库）
- 原著摘录
- 普通知识笔记
- AI 生成的建议（未经验证）
- 开发实验报告

## 目录组织

分类由真实内容推动，不预建空目录。当真实知识出现后，自然生长文件或少量分类。

## Agent 操作规则

- 只写入经多作品和真实创作验证的知识
- 不预建空 taxonomy
- 不以目录统一为由删除有价值内容
- 方法源（02 method 包）绝不自动升级进 04；进入 04 必须有显式的验证记录与
  `FINALIZED_VALIDATED` 定稿；未定稿包不可检索
