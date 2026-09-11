# -*- coding: utf-8 -*-
"""Canonical BookDistill Agent-task builder used by author-facing runtimes."""
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


def build_distill_agent_task(sp_dir: Path, bd_dir: Path) -> str:
    """Build the one canonical semantic task without duplicating it in Workbench."""
    sp = str(Path(sp_dir).resolve())
    bd = str(Path(bd_dir).resolve())
    scripts = _SKILL_ROOT / "scripts"
    scout = str((scripts / "profile_scout.py").resolve())
    observer_bridge = str((scripts / "observer_bridge.py").resolve())
    book_distill = str((scripts / "book_distill.py").resolve())
    acceptance_gate = str((scripts / "acceptance_gate.py").resolve())
    repo_root = str(_SKILL_ROOT.parents[2].resolve())
    contracts = _read_contracts()
    return f"""你是 Go Write 的 BookDistill 原著学习执行器。以下三个 FORMAL CONTRACT 是本次任务的正式语义合同，必须直接遵守，不得用概括版替代。

输入：
- SourcePrepare PASS 包：{sp}
- BookDistill staging：{bd}
- 原著章节：{sp}/chapters/（NNNN.md；0000_*.md 是卷首，不蒸馏）

严格执行顺序：
1. BookProfile Scout：运行 `python "{scout}" init --input "{sp}" --output "{bd}"`；直接阅读生成的锚点原文，填写 `{bd}/book_profile_initial.md`，保持 HYPOTHESIS / NAVIGATION ONLY；再运行对应 `validate`。它只导航，不能过滤后续观察。
2. 初始化观察工作区：运行 `python "{observer_bridge}" init --input "{sp}" --output "{bd}"`。
3. Base Scan：逐章直接阅读原著，在 `{bd}/evidence/ch_NNNN.md` 填写可追溯 MAP 与 FACT / INFERENCE / OBSERVATION / MECHANISM / BOUNDARY；每条引用 `chapters/NNNN.md#L起-L止`，含置信度，不大量复制原文。
4. 两个独立 Discovery Pass：分别严格按 `longform_reader_dynamics` 与 `reader_page_craft` 合同直接读原著并填写其 discovery/chapter 工件。不要从另一观察者摘要二次总结，不为覆盖率硬填。
5. 分别运行 observer_bridge.py `validate --observer <observer_id>`；两者都通过后运行 `merge`。桥只合并 OBSERVATION / INFERENCE / BOUNDARY，不会自动晋升 MECHANISM。
6. 只在初始 profile、观察合同或 Discovery 证据暴露真实专项问题时，运行 `python "{book_distill}" deepdive --output "{bd}" --dimension "<维度>" --topic "<问题>" --input "{sp}"`，直接读相关原文章节并填写、校验。没有真实触发器时 0 次 Deep Dive 合法，禁止为了流程完整硬造。
7. Editorial Convergence：跨章交叉验证、合并同质项、降级单章小技巧，保留反证/边界；形成 `{bd}/mechanisms.md`（10–20 条高价值可迁移机制）、`evidence.md`、`model.md` 与 `bd_report.md`。Discovery 可以宽，BKP 必须克制；不模仿原作者风格。
8. 运行 BookDistill `assemble` 与 `profile`，再依据 `book_profile.md`、全部证据、model、mechanisms 与 BKP_protocol.md 创建完整 `{bd}/bkp_prototype/`。知识卡必须可追溯，author_view 只是可读投影。
9. 写 `{bd}/BKP_ACCEPTANCE_REPORT.md`，包含 BKP_protocol.md §5 要求的 acceptance_data JSON；只对冻结来源范围下结论，连载/节选/未完结本身不是 blocking gap。
10. 在本次同一个 Agent turn 内完成确定性收口：依次运行
   - `python "{book_distill}" assemble --input "{sp}" --output "{bd}"`
   - `python "{book_distill}" profile --output "{bd}"`
   - `python "{book_distill}" bkp --output "{bd}"`
   - `python "{acceptance_gate}" "{bd}" --repo-root "{repo_root}" --write-identity`
   只有最后一条命令成功且 `{bd}/bkp/identity.json` 的 acceptance.status 为 PASS，才可报告 completed。REVIEW / PENDING 是内部可恢复状态，绝不是作者终态。
11. 若上述命令明确指出可修复的 coverage / evidence / identity 缺口，必须回到对应原文和观察工件修复后重跑受影响命令；最多进行 2 轮有界修复，不得靠降低门槛或伪造证据通过。来源缺失、SourcePrepare 身份不一致、原文不可读等硬失败应停止并报告 failed。
12. 不修改 SourcePrepare 输入。全部完成后只输出一个 JSON 对象：成功为 {{"status":"completed","evidence_files":<数量>,"mechanisms_count":<数量>}}；硬失败或两轮修复后仍不通过为 {{"status":"failed","reason":"简短可读原因"}}。

{contracts}
"""
