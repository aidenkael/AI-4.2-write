# -*- coding: utf-8 -*-
from pathlib import Path

from agent_task import build_distill_agent_task


def test_agent_task_consumes_formal_observer_contracts_and_full_pipeline(tmp_path: Path) -> None:
    task = build_distill_agent_task(tmp_path / "source", tmp_path / "distill")
    assert "FORMAL CONTRACT: book_profile_scout.md" in task
    assert "FORMAL CONTRACT: longform_reader_dynamics.md" in task
    assert "FORMAL CONTRACT: reader_page_craft.md" in task
    assert "profile_scout.py" in task
    assert "observer_bridge.py" in task
    assert "longform_reader_dynamics" in task and "reader_page_craft" in task
    assert "0 次 Deep Dive 合法" in task
    assert "Editorial Convergence" in task
    assert "BKP_ACCEPTANCE_REPORT.md" in task
    assert "acceptance_gate.py" in task
    assert "acceptance.status 为 PASS" in task
    assert "最多进行 2 轮有界修复" in task
    assert "REVIEW / PENDING" in task
