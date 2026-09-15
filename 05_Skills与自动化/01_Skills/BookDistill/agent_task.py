# -*- coding: utf-8 -*-
"""Canonical BookDistill Agent-task builder used by author-facing runtimes.

The author still clicks "原著学习" once and still sends a single ``/gowrite`` in
one Qoder Agent window. For ``book_distill_propose`` the ``/gowrite`` main Agent
executes this task *itself* as the BookDistill coordinator (Main): it no longer
hands the whole book to one general-purpose child that reads serially.

Main coordinates a **shared dynamic Reader pool** — it dispatches dedicated
one-batch ``gowrite-bookdistill-reader`` subagents (``subagent_type``), bounded
by a machine-wide global limit, and refills dynamically (no fixed wave barrier).
The project Custom Agent intentionally omits the ``model`` frontmatter field:
Qoder CN CLI 1.1.52 then inherits the parent/main session model at real spawn
time. Literal ``model: inherit`` is forbidden because some runtime paths parse
it as a concrete model id (40506); concrete Qwen/DeepSeek ids are forbidden too.
Each Reader reads exactly one batch's real prose, audits the six domains, and
atomically publishes one source-bound note; only Main commits to the on-disk
reading ledger (serial, in manifest order) and runs rolling → final whole-book
convergence, BKP, acceptance, and the bridge response envelope.

Long-term state lives only on disk (manifest / ledger / batch notes /
convergence_state), never in the chat window; resume is disk-authoritative.
Observers are *analytical perspectives*, not extra physical full-book scans.

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

# Parallel Reader orchestration facts mirrored into the task text. These MUST
# stay equal to ``reader_pool.READER_LIMIT`` and ``book_distill.READER_SUBAGENT_TYPE``;
# a focused test guards against drift so this builder stays import-decoupled.
READER_SUBAGENT = "gowrite-bookdistill-reader"
READER_LIMIT = 16


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
    return f"""你是 Go Write 的 BookDistill 原著学习**主编排 Agent（Main / coordinator）**。以下三个 FORMAL CONTRACT 是本次任务的正式语义合同，必须直接遵守，不得用概括版替代。

【执行架构（并行 Reader，不再单 child 串行读全书）】
- 你（Main）在本次 /gowrite 会话中**亲自执行** canonical BookDistill 编排；绝不把整本书包给单个 general-purpose 子 Agent 串行读完。
- 你通过 Qoder 的 Agent 工具、以 `subagent_type="{READER_SUBAGENT}"` 分派**专用单批次阅读器（Reader）**；每个 Reader 严格只负责一个 batch。
- `{READER_SUBAGENT}` 的项目级 Custom Agent frontmatter **故意省略 `model` 字段**；Qoder CN CLI 1.1.52 在真实 spawn 时据此继承当前 Main 会话模型。不得写 `model: inherit`，也不得硬编码任何 Qwen/DeepSeek model id。
- 所有同时进行的 Reader 合计受**全局共享 Reader 池上限 {READER_LIMIT}** 约束（多本 BookDistill 共用同一池），由确定性 lease 原语强制，你不得绕过或放大。
- **Main 独占职责**：BookProfile Scout、manifest/ledger 调度、Reader 分派、note 复核、**按 manifest 顺序串行 `reading-commit`**、滚动收敛、跨批冲突/边界判断、必要的原文定向回读、mechanisms/evidence/model/bd_report、bkp_prototype/BKP、acceptance、completion receipt、bridge response。
- **Reader 只做**：完整读取一个 batch 全部 span 的原文、六域 checked、写来源绑定 findings 到唯一 temp note、运行确定性 `note-publish` 原子发布 canonical note。Reader 绝不 `reading-commit`、绝不改 manifest/ledger/convergence/BKP/acceptance/response、绝不生成知识卡、绝不再分派子 Agent。

输入：
- SourcePrepare PASS 包：{sp}
- BookDistill staging：{bd}
- 原著输入单元：{sp}/chapters/（NNNN.md；单元语义以 metadata.unit_semantics 为准；0000_*.md 是前置）
- 本次请求 request_id：{rid}
- 专用 Reader 子 Agent：`{READER_SUBAGENT}`（项目级 Custom Agent，已在 .qoder/agents/ 定义；省略 model 字段以动态继承 Main 当前模型）
- BookDistill CLI：`{book_distill}`

核心纪律（超长原著可恢复真实遍历 + 并行 Reader）：
- 本书可能非常长（数百至数千章）。你**不需要**、也**不允许**一次性把全书读进上下文；阅读由多个 Reader 分批并行完成。
- BookDistill 已在 {bd}/_work/ 生成确定性 reading manifest 与 reading ledger，把全书拆成有界批次；长期状态只依赖磁盘工件（manifest/ledger/batch notes/convergence_state），绝不依赖聊天窗口记忆。聊天上下文可自然压缩。
- 不要要求作者开新窗口/新会话，不要增加作者步骤。中断后重新继续同一请求时，从磁盘恢复，绝不重做已完成批次。

严格执行顺序：

1. BookProfile Scout：运行 `python "{scout}" init --input "{sp}" --output "{bd}"`；直接阅读生成的锚点原文，填写 `{bd}/book_profile_initial.md`，保持 HYPOTHESIS / NAVIGATION ONLY；再运行对应 `validate`。它只导航，不能过滤后续观察。

2. 恢复与准备（每次开始或从中断恢复都先做，真相源是磁盘）：
   a. `python "{book_distill}" reading-status --output "{bd}"`：reload manifest + ledger 进度。
   b. `python "{book_distill}" reader-reconcile --output "{bd}"`：安全释放本 request 自己遗留的 Reader 租约（不会动其它书的租约）。
   c. 已完成（completed）的 ledger batch **永远不重派**；已完整写好但未 commit 的 canonical note 直接串行 commit（见第 3 步 commit_ready），不重读；写坏的 incomplete temp note 不算完成，丢弃后只重读该 batch。

3. 并行阅读循环（全书阅读完成度的唯一权威 = manifest/ledger；**动态补位，不做固定 wave barrier**）。重复直到 ledger 全部 completed：
   a. `python "{book_distill}" reader-dispatch --output "{bd}" --input "{sp}"`：
      - `dispatch != null`：取得一个 batch（含 spans、原文行范围、`temp_note_path`、`note_template`、`note_publish_command`、`lease_token`）；该命令已原子占用一个全局 Reader 租约。
      - `pool_full == true`：全局 Reader 池已满（{READER_LIMIT}），不要 busy-loop；先处理已完成 Reader 的 commit/release 再补位。
      - `dispatch == null` 且 `commit_ready` 非空：这些 pending batch 已有合法 canonical note，直接串行 `reading-commit`，不重读。
      - `dispatch == null` 且 `complete == true`：全书阅读已结算，跳到第 4 步。
   b. 对每个 dispatch，用 Agent 工具以 `subagent_type="{READER_SUBAGENT}"` 启动**一个** Reader，只交给它这一个 batch 的分派载荷（staging_dir、sp_dir、batch_id、spans、temp_note_path、note_template、note_publish_command、request_id/run_id/manifest_hash/source_fingerprint）。Reader 会**直接阅读该 batch 全部 span 的完整原文**（不抽样、不只读首部、不伪造 scan_refs、不凭记忆替代），六域 checked（故事与大纲 / 人物与关系 / 章节与场景 / 冲突与节奏 / 世界与题材 / 语言与读者体验；每域 `0 findings` 合法、“未检查”不合法），写 temp note 并运行 `note-publish` 原子发布 canonical note。尽量保持在飞 Reader 接近上限以最大化吞吐，但同一时间所有书合计 active Reader 永远 `<= {READER_LIMIT}`。
   c. 每个 Reader 完成后，你（Main）复核其 canonical note，然后**按 manifest 顺序串行**运行 `python "{book_distill}" reading-commit --output "{bd}" --batch <batch_id>`。只有 commit 成功该批才算 completed；多个 Reader 同时结束时也只有 Main 可 commit。
   d. commit 后释放该 Reader 租约：`python "{book_distill}" reader-release --lease <lease_token>`；随即用 `reader-dispatch` 立即补下一个 batch（acquire -> 1 Reader/1 batch -> 完成 -> 验证/发布 note -> Main 串行 commit -> release -> 立即补位）。
   e. 期间持续维护 `{bd}/_work/convergence_state.md`（滚动收敛状态，过程工件，**绝不进入 02**）：processed batch ids、mechanism clusters、accumulated evidence、conflicts/counterevidence、scope/boundary differences、unresolved questions、canonical candidates、supporting candidates。**优先持续补满 Reader，绝不让收敛把并行阅读重新串行化。**

4. 全部 ledger completed 后，必须再做一次**全书 final Editorial Convergence**（不能只用滚动中间态）：交叉验证、合并同质项、降级单章小技巧，保留反证/边界。归并只在 conditions / mechanism / scale / effect 四者语义实质等价时进行，绝不按文字相似去重；归并后保留全部来源 evidence 与 merged_from 关系，不得丢失 scope/boundary/counterevidence。无法确认等价时宁可分开。形成：
   - `{bd}/mechanisms.md`：可迁移机制集，**数量由来源决定，不设 10–20 条等任何配额**；
   - `{bd}/evidence.md`、`{bd}/model.md`、`{bd}/bd_report.md`。
   Discovery 可以宽，BKP 必须克制；不模仿原作者风格。

5. 只在专项问题真正需要时，运行 `python "{book_distill}" deepdive --output "{bd}" --dimension "<维度>" --topic "<问题>" --input "{sp}"`，定向回读相关原文章节并填写、校验。没有真实触发器时 0 次 Deep Dive 合法。

6. 运行 BookDistill `assemble` 与 `profile`，再依据 `book_profile.md`、全部证据、model、mechanisms 与 BKP_protocol.md 创建完整 `{bd}/bkp_prototype/`。canonical card 晋升原则：一个 finding 进入 canonical card 当且仅当它有真实来源证据、表达可迁移独立机制（非单纯剧情事实）、能描述适用条件/作用机制/作用尺度/预期效果的核心关系、有必要 scope/boundary/counterevidence、能提供有效 use_stages/problem_types/tags。单章出现不等于低价值，不能仅因出现次数少而删除。**supporting 收紧**：`bkp/knowledge/supporting.md` 只允许进入“已 convergence、来源绑定、非 canonical、但确有长期复用价值”的 finding；**禁止把所有 Reader raw findings 复制进 supporting**；raw batch notes/未合并 discovery/temp/leases/convergence_state 只留在 {bd}/_work（06），绝不进入 02。

7. 写 `{bd}/BKP_ACCEPTANCE_REPORT.md`，包含 BKP_protocol.md §5 要求的 acceptance_data JSON；只对冻结来源范围下结论，连载/节选/未完结本身不是 blocking gap。

8. 在本次同一会话内完成确定性收口：依次运行
   - `python "{book_distill}" assemble --input "{sp}" --output "{bd}"`
   - `python "{book_distill}" profile --output "{bd}"`
   - `python "{book_distill}" bkp --output "{bd}"`
   - `python "{acceptance_gate}" "{bd}" --repo-root "{repo_root}" --write-identity`
   acceptance_gate 会机械验证 reading manifest 覆盖、reading ledger 完整结算、六域 checked、权威计数一致，并在全部通过且状态为 PASS 时写出确定性 completion receipt。只有最后一条命令成功且 `{bd}/bkp/identity.json` 的 acceptance.status 为 PASS，才可进入第 10 步。REVIEW / PENDING 是内部可恢复状态，绝不是作者终态。

9. 若上述命令明确指出可修复的 coverage / evidence / identity / ledger 缺口，必须回到对应原文和工件修复后重跑受影响命令；最多进行 2 轮有界修复，不得靠降低门槛或伪造证据通过。来源缺失、SourcePrepare 身份不一致、原文不可读等硬失败应停止并按第 10 步写 failed response。

10. 【关键·任务结束的唯一标志】按 /gowrite 协议把最终结果写入 request 指定的 response_path：{resp}
   - 成功：写入 {{"schema":"gowrite_response/v1","request_id":"{rid}","status":"completed","result":{{"evidence_files":<数量>,"mechanisms_count":<数量>,"canonical_card_count":<数量>,"batches_completed":<数量>}}}}
   - 硬失败或两轮修复后仍不通过：写入 {{"schema":"gowrite_response/v1","request_id":"{rid}","status":"failed","error":"简短可读原因"}}
   - 写入前先用标准 JSON parser 自验证；绝不把未通过验证的 JSON 写入 response_path。
   - **只在聊天输出 JSON 不算完成任务**；必须把 response envelope 写入上述 response_path 文件。写入后立即停止，不再执行任何额外动作。

{contracts}
"""
