# G4-D 非写入分支检查

`authority: non_authority_simulation_only`

本文件只验证解析分支；下面语句都不是作者真实决定，不能生成 `author_decision` 或修改 Story State。

| 模拟自然语言 | 应识别动作 | 应否写状态 |
|---|---|---|
| “C 就按这个方向。” | choose | 若真实且无歧义，可先建 Decision Record，再判断是否只改 approved_plan |
| “三个都不对，我不想围着查系统转。” | reject_all | 否 |
| “先放着，我还没想好。” | defer | 否 |
| “A 和 C 好像都行。” | ambiguous / 未完成决定 | 否；重大差异仍重要时应最小澄清 |

真实本轮作者输入已在 `decisions/g4d-dec-001.md` 中判定为 `modify`。因此 G4-D 已覆盖 choose / modify / reject_all / defer 以及歧义保护的最小语义分支，其中只有 modify 来自真实作者并拥有 authority。
