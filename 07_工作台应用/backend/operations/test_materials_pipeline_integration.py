# -*- coding: utf-8 -*-
"""§16 temp-root 确定性纵切集成：一条真实素材管线闭环（零真实 AI / 零真实用户素材）。

source → intake/classification → pending_prepare → fixture/fake Prepare MD → purified
→ fake Agent distill staging(06) → finalize/publish(02) → KnowledgeRetrieve discoverable → writing

全部使用 temp root + 假 CLI/假 Agent；KnowledgeRetrieve discovery 用真实 registry（不 monkeypatch），
证明只有受控发布到 02 的定稿包才可被检索、才进入写作素材库。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.base import AgentRequest, AgentResult
from config.settings import AppSettings, SettingsStore
from operations import agent_runner
from operations import materials


def _use_direct(adapter_name="fake_distill_agent", cfg=None):
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter_name, direct_model="native-1", direct_custom_model=None,
    ))


def test_full_material_pipeline_closed_loop(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "01_原始素材" / "00_待入库").mkdir(parents=True)
    for d in ("01_原著", "02_技巧类", "03_其他"):
        (root / "01_原始素材" / d).mkdir(parents=True)
    (root / "01_原始素材" / "素材资产.json").write_text(
        json.dumps({"schema_version": "1.0", "assets": [], "containers": []}, ensure_ascii=False),
        encoding="utf-8")
    monkeypatch.setattr(materials, "get_repo_root", lambda: root)
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))

    # 1) source → 00_待入库（inbox 合同）
    content = b"integration-book-bytes"
    sha = hashlib.sha256(content).hexdigest()
    src = tmp_path / "集成书.epub"
    src.write_bytes(content)
    materials.import_material_files([{"path": str(src)}])

    # 2) 作者选批次类型 → 机械入库计划 → MaterialIntake 事务入库（不自动提纯）
    built = materials.build_intake_plan_from_inbox("REFERENCE_WORK")
    intake_result = materials.apply_material_intake(built["plan"])
    assert intake_result["ok"] is True and len(intake_result["new_ids"]) == 1
    asset_id = intake_result["new_ids"][0]

    # 3) pending_prepare（待提纯）
    mats = {m["id"]: m for m in materials.list_materials()["materials"]}
    assert mats[asset_id]["workflow_stage"] == "new"
    assert mats[asset_id]["state"] == "pending_prepare"
    assert mats[asset_id]["prepared_available"] is False

    # 4) fixture/fake Prepare MD（模拟 SourcePrepare PASS 产物）→ refresh 结算
    name = mats[asset_id]["name"]
    sp = root / "06_工作区" / "SourcePrepare" / f"{asset_id}_{name}"
    (sp / "chapters").mkdir(parents=True)
    (sp / "full.md").write_text("# full\n", encoding="utf-8")
    (sp / "metadata.json").write_text(json.dumps({
        "book_id": asset_id, "status": "PASS", "selected_source": {"format": ".epub", "sha256": sha},
    }, ensure_ascii=False), encoding="utf-8")
    materials.refresh_materials()

    # 5) purified（已提纯 = 真实当前 Markdown）
    mats = {m["id"]: m for m in materials.list_materials()["materials"]}
    assert mats[asset_id]["workflow_stage"] == "purified"
    assert mats[asset_id]["state"] == "pending_distill"
    assert mats[asset_id]["prepared_available"] is True
    assert mats[asset_id]["prepared_format"] == "MD"

    # 6) fake Agent 蒸馏：只写 06 staging → finalize → 受控发布到 02
    # 保留真实 _REPO_ROOT（KnowledgeRetrieve registry 从真实仓导入）；只把 BD/gate 脚本指向假路径。
    _use_direct(cfg=tmp_path)
    monkeypatch.setattr(materials.sys, "executable", "python")
    bd_script = tmp_path / "fakescripts" / "book_distill.py"
    bd_script.parent.mkdir(parents=True, exist_ok=True)
    bd_script.write_text("", encoding="utf-8")
    gate_script = bd_script.with_name("acceptance_gate.py")
    gate_script.write_text("", encoding="utf-8")
    monkeypatch.setattr(materials, "_BD_SCRIPT", bd_script)
    monkeypatch.setattr(materials, "_ACCEPTANCE_GATE_SCRIPT", gate_script)

    class _FakeAdapter:
        name = "fake_distill_agent"
        def run(self, request):
            return AgentResult(status="completed", output='{"status":"completed"}', agent=self.name)
        def cancel(self):
            return True
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (_FakeAdapter(), AgentRequest(task="")))

    def fake_run(cmd, **kw):
        cmd = [str(c) for c in cmd]
        if any("book_distill.py" in c for c in cmd) and cmd[2] == "bkp":
            out = Path(cmd[cmd.index("--output") + 1])  # 06 staging
            bkp = out / "bkp"
            (bkp / "knowledge").mkdir(parents=True, exist_ok=True)
            (bkp / "identity.json").write_text(json.dumps({
                "bkp_version": "0.3", "schema_status": "FINALIZED",
                "book": {"book_id": asset_id, "title": name, "author": ""},
                "source_snapshot": {"source_sha256": sha},
            }, ensure_ascii=False), encoding="utf-8")
            (bkp / "knowledge" / "cards.md").write_text("## K001\n- evidence: chapters/0001.md#L1\n", encoding="utf-8")
            (bkp / "author_view.md").write_text("## 总览\n可学习。\n", encoding="utf-8")
            (out / "BKP_ACCEPTANCE_REPORT.md").write_text("report\n", encoding="utf-8")
        if any("acceptance_gate.py" in c for c in cmd):
            identity_path = Path(cmd[2]) / "bkp" / "identity.json"
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            identity["acceptance"] = {"schema": "gowrite_bkp_acceptance/v1", "required": True, "status": "PASS"}
            identity_path.write_text(json.dumps(identity, ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
    monkeypatch.setattr(materials.subprocess, "run", fake_run)

    distill = materials.run_book_distill(asset_id)
    assert distill["status"] == "completed"
    # 发布到正式 02；staging 已移走
    published = root / "02_素材知识库" / f"{asset_id}_{name}" / "bkp" / "identity.json"
    assert published.exists()

    # 7) KnowledgeRetrieve 真实可发现 → writing（写作素材库）
    mats = {m["id"]: m for m in materials.list_materials()["materials"]}
    assert mats[asset_id]["workflow_stage"] == "writing"
    assert mats[asset_id]["state"] == "ready"
    assert mats[asset_id]["writing_callable"] is True
    assert mats[asset_id]["knowledge_package_kind"] == "BKP"

    # 详情只读投影一致
    detail = materials.get_material_detail(asset_id)
    assert detail["workflow_stage"] == "writing" and detail["writing_callable"] is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
