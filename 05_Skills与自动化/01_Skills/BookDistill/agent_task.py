# -*- coding: utf-8 -*-
"""Canonical BookDistill Agent-task builder used by author-facing runtimes.

The author still clicks "原著学习" once and still sends a single ``/gowrite`` in
one Qoder Agent window. BookDistill internally splits the frozen source into
bounded batches; the Agent reads each batch's real prose directly, writes a
batch note, and commits it to the on-disk reading ledger. Chat context may
compact naturally between batches — long-term state lives only on disk, never
in the chat window.

Observers are *analytical perspectives*, not extra physical full-book scans.
The Agent no longer re-reads the whole book three times.

The final step MUST write the bridge response envelope to the request's
``response_path`` (per the ``/gowrite`` protocol). Outputting a JSON object to
chat does NOT complete the task; a missing response envelope is exactly the
defect this contract closes.
"""
from __future__ import annotations

from pathlib import Path


_SKILL_ROOT = Path(__file__).resolve().parent
_OBSERVER_CONTRACTS = (
    "book_profile_scout.md",
    "longform_reader_dynamics.md",
    "reader_page_craft.md",
)


def _read_contracts() -> str:
    blocks: list[str] = []
    for filename in _OBSERVER_CONTRACTS:
        path = _SKILL_ROOT / "observers" / filename
        blocks.append(f"\n===== FORMAL CONTRACT: {filename} =====\n{path.read_text(encoding='utf-8').strip()}\n")
    return "\n".join(blocks)


def build_distill_agent_task(
    sp_dir: Path,
    bd_dir: Path,
    *,
    request_id: str | None = None,
    response_path: str | None = None,
) -> str:
    """Build the one canonical semantic task without duplicating it in Workbench.

    ``request_id`` / ``response_path`` are optional: when the Workbench creates
    the bridge request it passes them so the task text can name the exact
    response envelope location. When omitted (manual CLI runs) the task falls
    back to the generic ``/gowrite`` protocol wording.
    """
    sp = str(Path(sp_dir).resolve())
    bd = str(Path(bd_dir).resolve())
    scripts = _SKILL_ROOT / "scripts"
    scout = str((scripts / "profile_scout.py").resolve())
    book_distill = str((scripts / "book_distill.py").resolve())
    acceptance_gate = str((scripts / "acceptance_gate.py").resolve())
    repo_root = str(_SKILL_ROOT.parents[2].resolve())
    contracts = _read_contracts()

    rid = request_id or "<request_id>"
    resp = response_path or "<request 文件中 response_path 字段指定的路径>"
    return f"""你是 Go Write 的 BookDistill 原著学习执行器。以下三个 FORMAL CONTRACT 是本次任务的正式语义合同，必须直接遵守，不得用概括版替代。

输入：
- SourcePrepare PASS 包：{sp}
- BookDistill staging：{bd}
- 原著输入单元：{sp}/chapters/（NNNN.md；单元语义以 metadata.unit_semantics 为准；0000_*.md 是前置）
- 本次请求 request_id：{rid}

核心纪律（超长原著可恢复真实遍历）：
- 本书可能非常长（数百至数千章）。你**不需要**、也**不允许**一次性把全书读进上下文。
- BookDistill 已在 {bd}/_work/ 生成确定性 reading manifest 与 reading ledger，把全书拆成有界批次。
- 你在**同一个 /gowrite 会话**中逐批直接阅读原文、逐批写 batch note、逐批落盘。聊天上下文可以自然压缩；长期状态只依赖磁盘工件（manifest/ledger/batch notes），绝不依赖聊天窗口记忆。
- 不要要求作者开新窗口/新会话，不要增加作者步骤。中断后重新继续同一请求时，从第一个未完成批次恢复，绝不重做已完成批次。

严格执行顺序：

1. BookProfile Scout：运行 `python "{scout}" init --input "{sp}" --output "{bd}"`；直接阅读生成的锚点原文，填写 `{bd}/book_profile_initial.md`，保持 HYPOTHESIS / NAVIGATION ONLY；再运行对应 `validate`。它只导航，不能过滤后续观察。

2. 逐批真实阅读循环（这是本书阅读完成度的唯一权威来源）。重复以下步骤直到 ledger 全部 completed：
   a. 运行 `python "{book_distill}" reading-next --output "{bd}"`，取得下一个未完成 batch（含 span 列表、原文行范围、batch note 模板与 note_path）。若返回 `complete:true`，跳到第 3 步。
   b. **直接阅读该 batch 全部 span 的完整原文**（{sp}/chapters/NNNN.md 的对应行范围）。不得抽样、不得只读首部、不得用脚本伪造 scan_refs、不得凭记忆或摘要替代真实阅读。
   c. 在原文仍处于当前上下文时，从三个语义视角同时分析（Observer 是视角，不是额外两遍物理全文扫描）：
      - 基础/全局叙事观察（故事与大纲、结构、世界与题材）；
      - longform reader dynamics（长篇运行、读者动力、期待/兑现、信息债、情绪生态）；
      - reader/page craft（逐时刻读者体验、POV/声音/节奏、对话/潜台词/微观机巧）。
   d. 按 batch note 模板写本批 `{bd}/_work/batch_notes/<batch_id>.md`：必须填写六域 checked（故事与大纲 / 人物与关系 / 章节与场景 / 冲突与节奏 / 世界与题材 / 语言与读者体验），每域 `0 findings` 完全合法，但"未检查"不合法；记录来源绑定 findings（带 chapters/NNNN.md#Lx-Ly 证据）与待跨批核对问题；保留模板末尾的 JSON 块并填好 batch_id / six_domains_checked / finding_count。某批没有高价值发现完全合法，禁止为验收硬造知识。
   e. 运行 `python "{book_distill}" reading-commit --output "{bd}" --batch <batch_id>`。只有 commit 成功该批才算 completed。
   f. 继续下一批。

3. 全部批次 completed 后，做跨批次 Editorial Convergence：交叉验证、合并同质项、降级单章小技巧，保留反证/边界。归并只在 conditions / mechanism / scale / effect 四者语义实质等价时进行，绝不按文字相似去重；归并后保留全部来源 evidence 与 merged_from 关系，不得丢失 scope/boundary/counterevidence。无法确认等价时宁可分开。形成：
   - `{bd}/mechanisms.md`：可迁移机制集，**数量由来源决定，不设 10–20 条等任何配额**；
   - `{bd}/evidence.md`、`{bd}/model.md`、`{bd}/bd_report.md`。
   Discovery 可以宽，BKP 必须克制；不模仿原作者风格。

4. 只在专项问题真正需要时，运行 `python "{book_distill}" deepdive --output "{bd}" --dimension "<维度>" --topic "<问题>" --input "{sp}"`，定向回读相关原文章节并填写、校验。没有真实触发器时 0 次 Deep Dive 合法。

5. 运行 BookDistill `assemble` 与 `profile`，再依据 `book_profile.md`、全部证据、model、mechanisms 与 BKP_protocol.md 创建完整 `{bd}/bkp_prototype/`。canonical card 晋升原则：一个 finding 进入 canonical card 当且仅当它有真实来源证据、表达可迁移独立机制（非单纯剧情事实）、能描述适用条件/作用机制/作用尺度/预期效果的核心关系、有必要 scope/boundary/counterevidence、能提供有效 use_stages/problem_types/tags。单章出现不等于低价值，不能仅因出现次数少而删除。全面阅读产生但尚不足以晋升的来源绑定 finding 存入 BKP 非默认检索层（supporting），保留来源证据，绝不删除。

6. 写 `{bd}/BKP_ACCEPTANCE_REPORT.md`，包含 BKP_protocol.md §5 要求的 acceptance_data JSON；只对冻结来源范围下结论，连载/节选/未完结本身不是 blocking gap。

7. 在本次同一会话内完成确定性收口：依次运行
   - `python "{book_distill}" assemble --input "{sp}" --output "{bd}"`
   - `python "{book_distill}" profile --output "{bd}"`
   - `python "{book_distill}" bkp --output "{bd}"`
   - `python "{acceptance_gate}" "{bd}" --repo-root "{repo_root}" --write-identity`
   acceptance_gate 会机械验证 reading manifest 覆盖、reading ledger 完整结算、六域 checked、权威计数一致，并在全部通过且状态为 PASS 时写出确定性 completion receipt。只有最后一条命令成功且 `{bd}/bkp/identity.json` 的 acceptance.status 为 PASS，才可进入第 8 步。REVIEW / PENDING 是内部可恢复状态，绝不是作者终态。

8. 若上述命令明确指出可修复的 coverage / evidence / identity / ledger 缺口，必须回到对应原文和工件修复后重跑受影响命令；最多进行 2 轮有界修复，不得靠降低门槛或伪造证据通过。来源缺失、SourcePrepare 身份不一致、原文不可读等硬失败应停止并按第 9 步写 failed response。

9. 【关键·任务结束的唯一标志】按 /gowrite 协议把最终结果写入 request 指定的 response_path：{resp}
   - 成功：写入 {{"schema":"gowrite_response/v1","request_id":"{rid}","status":"completed","result":{{"evidence_files":<数量>,"mechanisms_count":<数量>,"canonical_card_count":<数量>,"batches_completed":<数量>}}}}
   - 硬失败或两轮修复后仍不通过：写入 {{"schema":"gowrite_response/v1","request_id":"{rid}","status":"failed","error":"简短可读原因"}}
   - 写入前先用标准 JSON parser 自验证；绝不把未通过验证的 JSON 写入 response_path。
   - **只在聊天输出 JSON 不算完成任务**；必须把 response envelope 写入上述 response_path 文件。写入后立即停止，不再执行任何额外动作。

{contracts}
"""
