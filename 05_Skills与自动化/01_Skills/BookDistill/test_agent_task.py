# -*- coding: utf-8 -*-
from pathlib import Path

from agent_task import build_distill_agent_task


def test_agent_task_consumes_formal_observer_contracts_and_full_pipeline(tmp_path: Path) -> None:
    task = build_distill_agent_task(tmp_path / "source", tmp_path / "distill")
    # 三个正式观察视角合同仍被直接纳入（Observer 是视角，不是额外两遍物理全文扫描）。
    assert "FORMAL CONTRACT: book_profile_scout.md" in task
    assert "FORMAL CONTRACT: longform_reader_dynamics.md" in task
    assert "FORMAL CONTRACT: reader_page_craft.md" in task
    assert "profile_scout.py" in task
    assert "longform_reader_dynamics" in task and "reader_page_craft" in task
    assert "0 次 Deep Dive 合法" in task
    assert "Editorial Convergence" in task
    assert "BKP_ACCEPTANCE_REPORT.md" in task
    assert "acceptance_gate.py" in task
    assert "acceptance.status 为 PASS" in task
    assert "最多进行 2 轮有界修复" in task
    assert "REVIEW / PENDING" in task


def test_agent_task_requires_resumable_batch_reading(tmp_path: Path) -> None:
    """合同：可恢复逐批真实阅读 + 磁盘 ledger，绝不要求一次读全书或三遍全文扫描。"""
    task = build_distill_agent_task(tmp_path / "source", tmp_path / "distill")
    # 并行编排：Main 用 reader-dispatch 取批 + 专用 Reader 子 Agent，串行 reading-commit。
    assert "reader-dispatch" in task
    assert "reading-commit" in task
    assert "reader-reconcile" in task and "reader-release" in task
    assert "note-publish" in task
    assert "直接阅读该 batch 全部 span 的完整原文" in task
    # 不再要求两名 Observer 各自重新完整读一遍全书。
    assert "observer_bridge.py" not in task
    # 六域 checked 审计（0 findings 合法，unchecked 不合法）。
    assert "故事与大纲" in task and "语言与读者体验" in task
    # 取消固定 card 数量配额（明确声明不设配额、数量由来源决定）。
    assert "数量由来源决定" in task
    assert "不设 10–20 条等任何配额" in task


def test_agent_task_is_main_coordinator_with_parallel_readers(tmp_path: Path) -> None:
    """新执行架构：Main=coordinator，专用单批次 Reader，全局共享池上限 16。"""
    task = build_distill_agent_task(tmp_path / "source", tmp_path / "distill")
    # Main 亲自编排，不再把整本书包给单个 general-purpose 子 Agent 串行读完。
    assert "主编排 Agent" in task
    assert "绝不把整本书包给单个 general-purpose 子 Agent" in task
    # 专用 Reader 子 Agent 以 subagent_type 分派，每个 Reader 只一个 batch。
    assert 'subagent_type="gowrite-bookdistill-reader"' in task
    assert "每个 Reader 严格只负责一个 batch" in task
    # 全局共享 Reader 池上限 16（多本共用），Reader 不得 reading-commit。
    assert "全局共享 Reader 池上限 16" in task
    assert "绝不 `reading-commit`" in task or "绝不 reading-commit" in task
    # Main 独占串行 commit。
    assert "按 manifest 顺序串行" in task
    assert "只有 Main 可 commit" in task
    # 滚动收敛状态是过程工件，绝不进入 02；全书 final convergence 仍必做。
    assert "convergence_state.md" in task
    assert "绝不进入 02" in task
    assert "final Editorial Convergence" in task
    # 动态补位、不做固定 wave barrier；恢复以磁盘为真相源。
    assert "动态补位" in task
    assert "completed）的 ledger batch **永远不重派**" in task or "永远不重派" in task


def test_agent_task_requires_response_envelope_not_chat_json(tmp_path: Path) -> None:
    """根因修复：任务结束的唯一标志是写 response envelope，不是只在聊天输出 JSON。"""
    task = build_distill_agent_task(
        tmp_path / "source", tmp_path / "distill",
        request_id="req123", response_path="/tmp/resp/req123.json",
    )
    assert "response_path" in task
    assert "/tmp/resp/req123.json" in task
    assert "req123" in task
    assert "gowrite_response/v1" in task
    assert "只在聊天输出 JSON 不算完成任务" in task
