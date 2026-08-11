# G3-B 最小跨书检索合同

> 版本：v0.1（G3-C 原型阶段）
> 建立日期：2026-08-11
> 对应 Gate：G3｜跨书知识库与创作任务检索
> 状态：候选合同，经 G3-C 原型验证。

---

## 1. 输入

检索接受：

- **作者的真实创作问题**（必填）：自然语言描述的创作困惑、需求或方向。
- **当前作品背景**（可选）：正在创作的作品类型、题材、目标。
- **创作目标/限制**（可选）：特定约束条件。

默认行为：
- 搜索全部已启用 BKP（当前：《一九八四》《三体》）。
- 返回约 3～8 条知识（允许少于 3 条，允许 INSUFFICIENT）。

---

## 2. 最小检索链

```text
结构化 BKP
→ 轻量候选召回（关键词/bigram 匹配 + 维度加分 + 置信度权重）
→ Agent 语义判断（相关性筛选 / 去重 / 排序）
→ TopK 输出
→ 完整知识卡
```

### 第一版明确不使用

- 向量数据库 / embedding 服务
- Qdrant / FAISS / Milvus
- Knowledge Graph
- Reranker 服务
- 大型 RAG 框架（LangChain / LlamaIndex 等）

只有真实验证证明轻量方案不足，才考虑升级。

---

## 3. Knowledge Hit（单条知识命中）

每条最终知识命中必须保留至少：

| 字段 | 说明 | 不可虚构 |
|---|---|---|
| `book_id` | 来源作品 ID | ✓ |
| `book_title` | 书名 | ✓ |
| `source_file` | BKP 来源文件 | ✓ |
| `source_anchor` | 条目锚点 | ✓ |
| `knowledge_level` | Observation / Inference / Work-specific Pattern / Deep Dive Knowledge | ✓ |
| `statement` | 知识内容 | ✓ |
| `relevance_reason` | 为什么与当前创作问题相关 | Agent 判断 |
| `evidence` | 章节/行号引用（已有时） | ✓ |
| `scope` | 适用范围（已有时） | ✓ |
| `boundary` | 适用边界（已有时） | ✓ |
| `counterevidence` | 反证（已有时） | ✓ |
| `confidence` | 置信度（已有时） | ✓ |

**不得为了统一结构虚构不存在的字段值。** 没有 boundary / counterevidence 时明确标记为 `absent`，不由程序编造。

---

## 4. Retrieval Package（完整检索包）

```json
{
  "query": "作者的创作问题",
  "query_understanding": "对创作意图的理解",
  "status": "OK | INSUFFICIENT_BKP",
  "candidate_count": 15,
  "hit_count": 5,
  "hits": [...],
  "gaps": ["知识库缺口说明"]
}
```

`status` 取值：
- `OK`：候选召回包含相关知识，经 Agent 语义筛选后输出。
- `INSUFFICIENT_BKP`：当前 BKP 中没有可靠知识回答该问题。

---

## 5. INSUFFICIENT_BKP

当两个 BKP 都没有可靠知识时，必须明确告诉上游"当前参考知识不足"，而不是硬拼不相关的知识。

触发条件（满足任一即可）：
- 关键词候选召回为零；
- 候选召回得分极低（全部低于阈值）；
- Agent 语义判断认为所有候选均与问题无关。

输出时附带 `gaps` 说明知识库当前缺口。

---

## 6. 知识等级边界

检索不自动升级知识等级：

- 即使两本书检索出了相似 Pattern，也只能报告"两个独立单书 Pattern 同时相关"。
- **不得自动生成 Cross-book Pattern。**
- 单书 Pattern 保持为 Work-specific Pattern Hypothesis。

Boundary 与知识主体不可分离：不能只召回一个 Pattern 却丢掉它的适用边界和反证。

---

## 7. 当前不使用大型 RAG 的决定

G3-C 原型验证结论（2026-08-11）：

对于当前两个 BKP（共 1151 条知识）+ 真实创作问题场景：

> **"轻量候选召回 + Agent 语义选择"已经足够。**

证据：
- Test A（偏单书）：15/15 候选均来自《三体》，得分高（1.579），语义全部相关。
- Test B（两本都可能有帮助）：三体悬念 Pattern 高度相关；一九八四"宣布式失败悬念"被关键词遗漏但 Agent 可补回。
- Test C（BKP 无答案）：得分极低（0.274），Agent 正确判定 INSUFFICIENT。
- Negative Test（语义误召回）：关键词召回有假阳性（~10/15），但 Agent 语义层可正确筛选至 ~3 条。

**结论：NO_RAG_UPGRADE。**

只有以下情况出现时才考虑升级：
- BKP 数量增长到 10+ 本，关键词召回精度显著下降；
- 知识条目增长到 10000+ 条，人工语义筛选成本过高；
- 真实创作中出现轻量方案无法解决的检索失败。

---

## 8. 不强求跨书 / 不强求填满

- 一个问题若只有《三体》相关，允许结果全部来自《三体》。
- 只有 2 条真正有价值，就返回 2 条。
- 禁止为了"跨书检索"的表面效果硬塞不相关知识。

---

## 9. 当前检索实现

| 组件 | 位置 | 说明 |
|---|---|---|
| Registry | `KnowledgeRetrieve/registry.py` | 扫描 `02_原著蒸馏/*/bkp/identity.json` 自动发现 BKP |
| Adapter | `KnowledgeRetrieve/adapter.py` | 解析 observations/inferences/patterns/boundaries/deep_dive 为统一结构 |
| Retrieve | `KnowledgeRetrieve/retrieve.py` | Chinese bigram + keyword 匹配，维度加分，置信度权重 |
| Runner | `KnowledgeRetrieve/run.py` | CLI 入口 + 输出 JSON RetrievalPackage |
| Models | `KnowledgeRetrieve/models.py` | KnowledgeItem / KnowledgeHit / RetrievalPackage 数据类 |

依赖：Python 标准库（无第三方依赖）。
