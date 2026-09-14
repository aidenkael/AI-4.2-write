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
    """新合同：逐批真实阅读 + 磁盘 ledger，绝不要求一次读全书或三遍全文扫描。"""
    task = build_distill_agent_task(tmp_path / "source", tmp_path / "distill")
    assert "reading-next" in task
    assert "reading-commit" in task
    assert "直接阅读该 batch 全部 span 的完整原文" in task
    # 不再要求两名 Observer 各自重新完整读一遍全书。
    assert "observer_bridge.py" not in task
    # 六域 checked 审计（0 findings 合法，unchecked 不合法）。
    assert "故事与大纲" in task and "语言与读者体验" in task
    # 取消固定 card 数量配额（明确声明不设配额、数量由来源决定）。
    assert "数量由来源决定" in task
    assert "不设 10–20 条等任何配额" in task


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
