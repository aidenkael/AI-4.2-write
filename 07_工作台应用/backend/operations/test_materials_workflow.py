# -*- coding: utf-8 -*-
"""素材工作流 targeted tests（全部假 adapter / 假 CLI / temp root，无真实模型调用）。

覆盖：
A. 文件导入只进入 00_待入库（inbox 合同），绝不写入最终 canonical 目录；
B. 确定性事实优先：exact duplicate → ATTACH_EXISTING、unsupported → REVIEW，
   无需 Agent；
C. 无法定论文件 → 一次 Agent 分类 turn（Direct 假 adapter）；
D. Agent 输出校验：只接受 MaterialIntake 允许决策；编造 asset_id / 类型非法拒绝；
E. 分类后仍走 MaterialIntake 事务入库（apply 不被绕过）；
F. 显式 SourcePrepare：真实 SP CLI 被调用（subprocess 假）；失败传播；
G. 显式 BookDistill：validate/prepare/assemble/profile/bkp 阶段被调用；
   SourcePrepare 未 PASS 时拒绝；
H. 页面加载零模型：list_materials 无 Agent/Skill 调用（隐式）。
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

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "MaterialIntake"))


def _use_direct(adapter_name: str = "fake_classify_agent") -> None:
    SettingsStore().save(AppSettings(
        default_execution_mode="direct",
        interactive_agent="qoder",
        direct_agent=adapter_name,
        direct_model="native-1",
        direct_custom_model=None,
    ))


class _ClassifyAdapter:
    name = "fake_classify_agent"

    def __init__(self, decisions_json):
        self.calls = 0
        self.decisions_json = decisions_json

    def run(self, request):
        self.calls += 1
        return AgentResult(status="completed", output=self.decisions_json, agent=self.name)

    def cancel(self):
        return True


def _empty_ledger():
    return {"schema_version": "1.0", "assets": [], "containers": []}


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "01_原始素材" / "00_待入库").mkdir(parents=True)
    monkeypatch.setattr(materials, "get_repo_root", lambda: root)
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return root


def _write_ledger(root, ledger=None):
    path = root / "01_原始素材" / "素材资产.json"
    path.write_text(json.dumps(ledger or _empty_ledger(), ensure_ascii=False), encoding="utf-8")
    return path


def _fake_asset_ledger(asset_id="book_0001", name="样例作品", mtype="REFERENCE_WORK",
                       pur="可用", know="未开始"):
    return {
        "schema_version": "1.0",
        "assets": [{
            "id": asset_id, "name": name, "type": mtype, "author": "", "tags": [], "notes": "",
            "files": [{"path": "01_参考作品/样例作品/样例.epub", "sha256": "a" * 64, "primary": True}],
            "purification": {"status": pur},
            "knowledge": {"status": know},
        }],
        "containers": [],
    }


# ---------------------------------------------------------------------------
# A. 文件导入只进入 inbox
# ---------------------------------------------------------------------------

def test_import_stages_only_to_inbox(isolated, tmp_path):
    src = tmp_path / "sample.epub"
    src.write_bytes(b"fake-epub-content")
    result = materials.import_material_files([{"path": str(src)}])
    assert len(result["imported"]) == 1
    dest = isolated / "01_原始素材" / "00_待入库" / "sample.epub"
    assert dest.read_bytes() == b"fake-epub-content"
    # 绝不写入最终 canonical 目录（无 01_参考作品/01_研究资料 等创建）
    for sub in ("01_参考作品", "01_研究资料", "01_零散素材"):
        assert not (isolated / sub).exists(), f"导入不得直接写 {sub}"


def test_import_rejects_unsupported_and_missing(isolated, tmp_path):
    bad = tmp_path / "notes.docx"
    bad.write_bytes(b"x")
    result = materials.import_material_files([{"path": str(bad)}, {"path": str(tmp_path / "nope.epub")}])
    assert result["imported"] == []
    assert len(result["skipped"]) == 2


def test_import_avoids_inbox_collision(isolated, tmp_path):
    src = tmp_path / "sample.epub"
    src.write_bytes(b"a")
    (isolated / "01_原始素材" / "00_待入库" / "sample.epub").write_bytes(b"existing")
    result = materials.import_material_files([{"path": str(src)}])
    dest = isolated / "01_原始素材" / "00_待入库" / "sample-1.epub"
    assert dest.read_bytes() == b"a"
    assert (isolated / "01_原始素材" / "00_待入库" / "sample.epub").read_bytes() == b"existing"


# ---------------------------------------------------------------------------
# B. 确定性事实优先（无需 Agent）
# ---------------------------------------------------------------------------

def test_classify_deterministic_duplicate_and_unsupported(isolated, monkeypatch):
    ledger = _fake_asset_ledger()
    dup_content = b"dup-content"
    ledger["assets"][0]["files"][0]["sha256"] = hashlib.sha256(dup_content).hexdigest()
    _write_ledger(isolated, ledger)
    (isolated / "01_原始素材" / "00_待入库" / "dup.epub").write_bytes(dup_content)
    (isolated / "01_原始素材" / "00_待入库" / "notes.docx").write_bytes(b"x")

    built = []
    def _must_not_build():
        built.append("build")
        raise AssertionError("确定性路径不得调用 Agent")
    monkeypatch.setattr(agent_runner, "_build_adapter", _must_not_build)

    result = materials.classify_material_inbox()
    assert result["status"] == "ready"
    assert result["agent_required"] is False
    assert built == []
    actions = {item["action"] for item in result["plan"]["items"]}
    assert "ATTACH_EXISTING" in actions  # 重复文件确定性并入
    assert "REVIEW" in actions            # 不支持类型确定性人工确认
    # 没有 NEW_ASSET（没有任何文件需要 Agent 判断）
    assert "NEW_ASSET" not in actions


# ---------------------------------------------------------------------------
# C/D. 无法定论文件 → 一次 Agent 分类 + 输出校验
# ---------------------------------------------------------------------------

def test_classify_ambiguous_routes_one_agent_turn(isolated, monkeypatch):
    _use_direct()
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")

    adapter = _ClassifyAdapter(json.dumps({
        "items": [{"filename": "新书.epub", "action": "NEW_ASSET", "name": "新书", "type": "REFERENCE_WORK"}],
    }, ensure_ascii=False))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="")))

    result = materials.classify_material_inbox()
    assert result["status"] == "ready"
    assert adapter.calls == 1, "一次分类 turn 最多一次"
    assert result["agent_used"] is True
    assert result["plan"]["items"][0]["action"] == "NEW_ASSET"
    assert result["plan"]["items"][0]["name"] == "新书"


def test_classify_agent_cannot_invent_asset_id(isolated, monkeypatch):
    _use_direct()
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")

    adapter = _ClassifyAdapter(json.dumps({
        "items": [{"filename": "新书.epub", "action": "ATTACH_EXISTING", "asset_id": "book_9999"}],
    }, ensure_ascii=False))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="")))
    # 台账中不存在 book_9999 → 校验拒绝（允许的决策集合校验以台账为准）
    with pytest.raises(materials.MaterialsError):
        materials.classify_material_inbox()


def test_classify_agent_bad_type_rejected(isolated, monkeypatch):
    _use_direct()
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")
    adapter = _ClassifyAdapter(json.dumps({
        "items": [{"filename": "新书.epub", "action": "NEW_ASSET", "name": "新书", "type": "BAD_TYPE"}],
    }, ensure_ascii=False))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="")))
    with pytest.raises(materials.MaterialsError):
        materials.classify_material_inbox()


def test_classify_agent_cannot_reference_unscanned_file(isolated, monkeypatch):
    _use_direct()
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")
    adapter = _ClassifyAdapter(json.dumps({
        "items": [{"filename": "不存在.epub", "action": "NEW_ASSET", "name": "X", "type": "REFERENCE_WORK"}],
    }, ensure_ascii=False))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="")))
    with pytest.raises(materials.MaterialsError):
        materials.classify_material_inbox()


def test_classify_interactive_accepts_structured_result(isolated, monkeypatch):
    """交互分类：结构化 result（NEW_ASSET + METHOD_SOURCE）经桥消费与文本 output 等效。"""
    from operations import qoder_bridge as bridge
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated.parent / ".bridge")
    SettingsStore().save(AppSettings(
        default_execution_mode="interactive_bridge",
        interactive_agent="qoder",
        direct_agent="fake_classify_agent",
        direct_model="native-1",
        direct_custom_model=None,
    ))
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "方法书.epub").write_bytes(b"method-book")

    pending = materials.classify_material_inbox()
    assert pending["status"] == "pending"
    assert pending["agent_required"] is True
    rid = pending["request_id"]

    # canonical 信封：结构化 result 直接放对象（新 /gowrite 契约）
    bridge.write_response(rid, result={
        "items": [{
            "filename": "方法书.epub", "action": "NEW_ASSET",
            "name": "人物弧光方法书", "type": "METHOD_SOURCE",
            "reason": "写作方法教程",
        }],
    })
    status = materials.get_material_classify_request(rid)
    assert status["status"] == "completed", status.get("error")
    item = status["plan"]["items"][0]
    assert item["action"] == "NEW_ASSET"
    assert item["name"] == "人物弧光方法书"
    assert item["type"] == "METHOD_SOURCE"


# ---------------------------------------------------------------------------
# E. 分类后仍走 MaterialIntake 事务入库
# ---------------------------------------------------------------------------

def test_classified_plan_applies_through_materialintake(isolated, monkeypatch):
    _use_direct()
    from operations import materials as m
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")
    adapter = _ClassifyAdapter(json.dumps({
        "items": [{"filename": "新书.epub", "action": "NEW_ASSET", "name": "新书", "type": "REFERENCE_WORK"}],
    }, ensure_ascii=False))
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="")))
    result = materials.classify_material_inbox()
    assert result["status"] == "ready"

    catalog, intake, post_action = m._load_materialintake()
    applied = {}
    monkeypatch.setattr(post_action, "precheck", lambda root: (True, "OK"))
    monkeypatch.setattr(intake, "apply_plan", lambda plan, ledger, root: (applied.update(plan=plan) or {"ok": True, "new_ids": ["book_0002"], "errors": []}))
    monkeypatch.setattr(post_action, "safe_commit_push", lambda root, allowlist, msg: "NO_TRACKED_CHANGES")

    outcome = materials.apply_material_intake(result["plan"])
    assert outcome["ok"] is True
    assert applied["plan"]["items"][0]["action"] == "NEW_ASSET", "Agent 决策经事务 apply，不绕过 MaterialIntake"


# ---------------------------------------------------------------------------
# F. 显式 SourcePrepare（真实 SP CLI 被调用；失败传播）
# ---------------------------------------------------------------------------

def test_run_source_prepare_invokes_real_cli(isolated, monkeypatch):
    _write_ledger(isolated, _fake_asset_ledger())
    script = isolated.parent / "sp.py"
    calls = []

    monkeypatch.setattr(materials, "_REPO_ROOT", isolated.parent)
    monkeypatch.setattr(materials.sys, "executable", "python")
    sp_script = materials._REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "SourcePrepare" / "scripts" / "source_prepare.py"
    sp_script.parent.mkdir(parents=True)
    sp_script.write_text("", encoding="utf-8")

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="PASS book_0001\n", stderr="")

    monkeypatch.setattr(materials.subprocess, "run", fake_run)
    result = materials.run_source_prepare("book_0001")
    assert result["status"] == "completed"
    assert "--book" in calls[0] and "book_0001" in calls[0]


def test_run_source_prepare_failure_propagates(isolated, monkeypatch):
    _write_ledger(isolated, _fake_asset_ledger())
    monkeypatch.setattr(materials, "_REPO_ROOT", isolated.parent)
    monkeypatch.setattr(materials.sys, "executable", "python")
    sp_script = materials._REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "SourcePrepare" / "scripts" / "source_prepare.py"
    sp_script.parent.mkdir(parents=True)
    sp_script.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        materials.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="EPUB FAIL"),
    )
    with pytest.raises(materials.MaterialsError) as ei:
        materials.run_source_prepare("book_0001")
    assert "提纯失败" in str(ei.value)


def test_run_source_prepare_rejects_loose_material(isolated):
    _write_ledger(isolated, _fake_asset_ledger(mtype="LOOSE_MATERIAL"))
    with pytest.raises(materials.MaterialsError, match="不适用提纯"):
        materials.run_source_prepare("book_0001")


# ---------------------------------------------------------------------------
# G. 显式 BookDistill（真实 BD CLI 阶段；未 PASS 拒绝）
# ---------------------------------------------------------------------------

def test_run_book_distill_requires_pass_input(isolated, monkeypatch):
    _write_ledger(isolated, _fake_asset_ledger(pur="可用"))
    monkeypatch.setattr(materials, "_REPO_ROOT", isolated.parent)
    monkeypatch.setattr(materials.sys, "executable", "python")
    bd_script = materials._REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "BookDistill" / "scripts" / "book_distill.py"
    bd_script.parent.mkdir(parents=True)
    bd_script.write_text("", encoding="utf-8")

    # 没有 SP 输出目录 → 拒绝（必须先生成 PASS 提纯产物）
    with pytest.raises(materials.MaterialsError, match="还没有任何提纯产物"):
        materials.run_book_distill("book_0001")


def test_run_book_distill_deterministic_stages(isolated, monkeypatch):
    _use_direct("fake_distill_agent")
    _write_ledger(isolated, _fake_asset_ledger(pur="可用"))
    monkeypatch.setattr(materials, "_REPO_ROOT", isolated.parent)
    monkeypatch.setattr(materials.sys, "executable", "python")
    bd_script = materials._REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "BookDistill" / "scripts" / "book_distill.py"
    bd_script.parent.mkdir(parents=True)
    bd_script.write_text("", encoding="utf-8")
    sp_dir = isolated / "06_工作区" / "SourcePrepare" / "book_0001_样例作品"
    sp_dir.mkdir(parents=True)

    class _FakeAdapter:
        name = "fake_distill_agent"
        def run(self, request):
            return AgentResult(status="completed", output='{"status": "completed"}', agent=self.name)
        def cancel(self):
            return True

    adapter = _FakeAdapter()
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (adapter, AgentRequest(task="")))
    calls = []
    catalog, _, _ = materials._load_materialintake()

    def fake_run(cmd, **kw):
        if any("book_distill.py" in str(c) for c in cmd):
            calls.append(cmd[2])  # 子命令：validate/prepare/assemble/profile/bkp
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(materials.subprocess, "run", fake_run)
    monkeypatch.setattr(catalog, "refresh_and_render", lambda root, check_only: 0)

    result = materials.run_book_distill("book_0001")
    assert result["status"] == "completed"
    # validate + prepare 后进入 Agent 阶段，再 assemble/profile/bkp
    assert "validate" in calls and "prepare" in calls
    assert calls.count("assemble") >= 1 and calls.count("profile") >= 1 and calls.count("bkp") >= 1
    assert adapter is not None


# ---------------------------------------------------------------------------
# H. 页面加载零模型（隐式）
# ---------------------------------------------------------------------------

def test_list_materials_zero_model_calls(isolated, monkeypatch):
    _write_ledger(isolated, _fake_asset_ledger())
    built = []
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (built.append(1), None)[1])
    result = materials.list_materials()
    assert len(result["materials"]) == 1
    assert built == [], "页面加载绝不调用 Agent"

    # 详情也只读
    detail = materials.get_material_detail("book_0001")
    assert detail["writing_callable"] is False
    assert detail["stage"] == "提纯完成，待蒸馏"
