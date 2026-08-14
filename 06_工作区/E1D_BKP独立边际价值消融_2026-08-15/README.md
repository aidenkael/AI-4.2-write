# E1-D｜BKP 独立边际价值消融测试

状态：`TECHNICAL_EVIDENCE_READY / E1_PASS_NOT_DECLARED`

目标：在“同一自由初稿 + 同一 W1/W2 诊断 + 各一次二次修订”已经固定的条件下，只改变 C1 是否看到 K016，验证 BKP 相对强模型自身二次思考的独立边际价值。

- `c0_no_bkp/`：不读取 BKP、不调用 KnowledgeRetrieve。
- `c1_with_bkp/`：只额外读取冻结的 K016；W2 继续为 `NO_USEFUL_BKP`。
- `blind/`：随机 X/Y 包装及评审共同输入。

所有产物均为 disposable、`proposal_noncanonical`。不修改正式代码、长期手册、Story State；不进入 StoryPlan / Writer。

解盲后的窄证据结论为 `BKP_INDEPENDENT_VALUE_SUPPORTED`：仅支持 K016 对 W1 跨情境职业动作与人物心智累积的小幅独立增益，不代表 BKP 普遍必需，也不宣布整个 E1 通过。详见 `internal_attribution.md` 与 `technical_report.md`。
