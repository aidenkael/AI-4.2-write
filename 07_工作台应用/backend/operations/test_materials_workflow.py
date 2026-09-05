"""素材工作流 targeted tests（全部假 adapter / 假 CLI / temp root，无真实模型调用）。

覆盖：
A. 文件导入只进入 00_待入库（inbox 合同），绝不写入最终 canonical 目录；
B. 批次机械入库计划（零 AI）：build_intake_plan_from_inbox；
   exact_duplicate → ATTACH_EXISTING、unsupported → REVIEW、其余 → NEW_ASSET；
C. 格式白名单：只允许 .epub/.pdf/.txt，拒绝 .zip/.mobi/.azw3/.docx；
D. 批次类型映射：REFERENCE_WORK / METHOD_SOURCE / LOOSE_MATERIAL；无效类型报错；
E. 入库计划经 MaterialIntake 事务入库（apply 不被绕过）；
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
# B. 批次机械入库计划（零 AI）
# ---------------------------------------------------------------------------

def test_build_intake_plan_duplicate_and_unsupported(isolated, monkeypatch):
    """exact_duplicate → ATTACH_EXISTING、unsupported → REVIEW，零 Agent 调用。"""
    ledger = _fake_asset_ledger()
    dup_content = b"dup-content"
    ledger["assets"][0]["files"][0]["sha256"] = hashlib.sha256(dup_content).hexdigest()
    _write_ledger(isolated, ledger)
    (isolated / "01_原始素材" / "00_待入库" / "dup.epub").write_bytes(dup_content)
    (isolated / "01_原始素材" / "00_待入库" / "notes.docx").write_bytes(b"x")

    built = []
    def _must_not_build():
        built.append("build")
        raise AssertionError("机械入库计划不得调用 Agent")
    monkeypatch.setattr(agent_runner, "_build_adapter", _must_not_build)

    result = materials.build_intake_plan_from_inbox("REFERENCE_WORK")
    assert result["status"] == "ready"
    assert built == []
    actions = {item["action"] for item in result["plan"]["items"]}
    assert "ATTACH_EXISTING" in actions
    assert "REVIEW" in actions
    assert "NEW_ASSET" not in actions


def test_build_intake_plan_new_asset_uses_batch_type(isolated):
    """新文件 → NEW_ASSET，类型等于作者选择的批次类型。"""
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")

    result = materials.build_intake_plan_from_inbox("METHOD_SOURCE")
    assert result["status"] == "ready"
    new_items = [item for item in result["plan"]["items"] if item["action"] == "NEW_ASSET"]
    assert len(new_items) == 1
    assert new_items[0]["type"] == "METHOD_SOURCE"
    assert new_items[0]["name"] == "新书"


def test_build_intake_plan_invalid_batch_type(isolated):
    """无效批次类型 → MaterialsError。"""
    _write_ledger(isolated, _empty_ledger())
    with pytest.raises(materials.MaterialsError, match="批次类型无效"):
        materials.build_intake_plan_from_inbox("BAD_TYPE")


def test_build_intake_plan_empty_inbox(isolated):
    """空收件箱 → 空计划。"""
    _write_ledger(isolated, _empty_ledger())
    result = materials.build_intake_plan_from_inbox("REFERENCE_WORK")
    assert result["status"] == "ready"
    assert result["plan"]["items"] == []
    assert "没有需要入库" in result["message"]


# ---------------------------------------------------------------------------
# C. 格式白名单
# ---------------------------------------------------------------------------

def test_import_format_whitelist_rejects_zip_mobi_azw3(isolated, tmp_path):
    """已移除的格式（zip/mobi/azw3）不得导入。"""
    for suffix in (".zip", ".mobi", ".azw3"):
        bad = tmp_path / f"bad{suffix}"
        bad.write_bytes(b"x")
        result = materials.import_material_files([{"path": str(bad)}])
        assert result["imported"] == [], f"{suffix} 应被拒绝"
        assert len(result["skipped"]) == 1


def test_import_accepts_epub_pdf_txt(isolated, tmp_path):
    """白名单格式全部接受。"""
    for suffix in (".epub", ".pdf", ".txt"):
        src = tmp_path / f"book{suffix}"
        src.write_bytes(b"content")
        result = materials.import_material_files([{"path": str(src)}])
        assert len(result["imported"]) == 1, f"{suffix} 应被接受"


# ---------------------------------------------------------------------------
# D. 批次类型映射
# ---------------------------------------------------------------------------

def test_build_intake_plan_reference_work(isolated):
    _write_ledger(isolated, _empty_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "原著.epub").write_bytes(b"ref")
    result = materials.build_intake_plan_from_inbox("REFERENCE_WORK")
    item = result["plan"]["items"][0]
    assert item["type"] == "REFERENCE_WORK"


def test_build_intake_plan_loose_material(isolated):
    _write_ledger(isolated, _empty_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "杂项.txt").write_bytes(b"loose")
    result = materials.build_intake_plan_from_inbox("LOOSE_MATERIAL")
    item = result["plan"]["items"][0]
    assert item["type"] == "LOOSE_MATERIAL"


# ---------------------------------------------------------------------------
# E. 入库计划经 MaterialIntake 事务入库
# ---------------------------------------------------------------------------

def test_batch_plan_applies_through_materialintake(isolated, monkeypatch):
    """批次计划的 NEW_ASSET 经事务 apply，不绕过 MaterialIntake。"""
    from operations import materials as m
    _write_ledger(isolated, _fake_asset_ledger())
    (isolated / "01_原始素材" / "00_待入库" / "新书.epub").write_bytes(b"new-book")

    result = materials.build_intake_plan_from_inbox("REFERENCE_WORK")
    assert result["status"] == "ready"

    catalog, intake, post_action = m._load_materialintake()
    applied = {}
    monkeypatch.setattr(post_action, "precheck", lambda root: (True, "OK"))
    monkeypatch.setattr(intake, "apply_plan", lambda plan, ledger, root: (applied.update(plan=plan) or {"ok": True, "new_ids": ["book_0002"], "errors": []}))
    monkeypatch.setattr(post_action, "safe_commit_push", lambda root, allowlist, msg: "NO_TRACKED_CHANGES")

    outcome = materials.apply_material_intake(result["plan"])
    assert outcome["ok"] is True
    assert applied["plan"]["items"][0]["action"] == "NEW_ASSET", "批次计划经事务 apply，不绕过 MaterialIntake"


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
    gate_script = bd_script.with_name("acceptance_gate.py")
    gate_script.write_text("", encoding="utf-8")
    monkeypatch.setattr(materials, "_ACCEPTANCE_GATE_SCRIPT", gate_script)

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
    gate_script = bd_script.with_name("acceptance_gate.py")
    gate_script.write_text("", encoding="utf-8")
    monkeypatch.setattr(materials, "_ACCEPTANCE_GATE_SCRIPT", gate_script)
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
            if cmd[2] == "bkp":
                bkp = isolated / "02_素材知识库" / "book_0001_样例作品" / "bkp"
                (bkp / "knowledge").mkdir(parents=True, exist_ok=True)
                (bkp / "identity.json").write_text(json.dumps({"book": {"book_id": "book_0001", "title": "样例作品"}}, ensure_ascii=False), encoding="utf-8")
                (bkp / "knowledge" / "cards.md").write_text("## K001\n", encoding="utf-8")
                (bkp / "author_view.md").write_text("## 总览\n可学习。\n", encoding="utf-8")
        if any("acceptance_gate.py" in str(c) for c in cmd):
            calls.append("acceptance")
            identity_path = isolated / "02_素材知识库" / "book_0001_样例作品" / "bkp" / "identity.json"
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            identity["acceptance"] = {"required": True, "status": "PASS"}
            identity_path.write_text(json.dumps(identity, ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(materials.subprocess, "run", fake_run)
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    monkeypatch.setattr(catalog, "refresh_and_render", lambda root, check_only: 0)

    result = materials.run_book_distill("book_0001")
    assert result["status"] == "completed"
    # validate + prepare 后进入 Agent 阶段，再 assemble/profile/bkp
    assert "validate" in calls and "prepare" in calls
    assert calls.count("assemble") >= 1 and calls.count("profile") >= 1 and calls.count("bkp") >= 1
    assert "acceptance" in calls
    assert adapter is not None


def test_new_reference_distill_does_not_skip_missing_bkp_prototype(isolated, monkeypatch):
    """新书 Agent 未产出 curated 原型时，绝不能跳过 BKP/验收假装完成。"""
    _use_direct("fake_distill_agent")
    _write_ledger(isolated, _fake_asset_ledger(pur="可用"))
    monkeypatch.setattr(materials, "_REPO_ROOT", isolated.parent)
    monkeypatch.setattr(materials.sys, "executable", "python")
    script = materials._REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "BookDistill" / "scripts" / "book_distill.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    (isolated / "06_工作区" / "SourcePrepare" / "book_0001_样例作品").mkdir(parents=True)
    monkeypatch.setattr(agent_runner, "_build_adapter", lambda: (type("A", (), {"name": "fake", "run": lambda self, req: AgentResult(status="completed", output="{}", agent="fake")})(), AgentRequest(task="")))

    def fake_run(cmd, **kw):
        code = 1 if any("book_distill.py" in str(part) for part in cmd) and cmd[2] == "bkp" else 0
        return subprocess.CompletedProcess(cmd, code, stdout="missing bkp_prototype", stderr="")

    monkeypatch.setattr(materials.subprocess, "run", fake_run)
    with pytest.raises(materials.MaterialsError, match="学习资料整理失败"):
        materials.run_book_distill("book_0001")
    assert not (isolated / "02_素材知识库" / "book_0001_样例作品" / "bkp" / "identity.json").exists()


def test_interactive_book_distill_uses_exact_meta_asset_id(isolated, monkeypatch):
    """交互任务的资产身份来自 request meta，绝不从目录名反推。"""
    from operations import qoder_bridge as bridge
    request_id = "request-book-0035"
    request = {
        "state": "pending",
        "meta": {
            "asset_id": "book_0035",
            "sp_dir": str(isolated / "06_工作区" / "SourcePrepare" / "book_0035_长安十二时辰"),
            "bd_dir": str(isolated / "02_素材知识库" / "book_0035_长安十二时辰"),
        },
    }
    monkeypatch.setattr(bridge, "get_request", lambda rid: request)
    monkeypatch.setattr(bridge, "is_expired", lambda value: False)
    monkeypatch.setattr(bridge, "read_response", lambda rid: {"request_id": request_id, "status": "completed"})
    captured = {}
    monkeypatch.setattr(materials, "_finalize_distill", lambda rid, asset_id, sp_dir, bd_dir: captured.update(asset_id=asset_id, sp_dir=sp_dir, bd_dir=bd_dir) or {"status": "completed"})

    result = materials.get_book_distill_request(request_id)
    assert result["status"] == "completed"
    assert captured["asset_id"] == "book_0035"
    assert captured["bd_dir"].name == "book_0035_长安十二时辰"


def test_interactive_finalize_never_parses_directory_for_asset_id(isolated, monkeypatch):
    from operations import qoder_bridge as bridge
    looked_up = []
    monkeypatch.setattr(materials, "_ledger_asset", lambda asset_id: looked_up.append(asset_id) or {"id": asset_id})
    monkeypatch.setattr(materials, "_finalize_reference_distill", lambda *args: None)
    catalog = type("Catalog", (), {"refresh_and_render": staticmethod(lambda root, check_only=False: 0)})()
    monkeypatch.setattr(materials, "_load_materialintake", lambda: (catalog, None, None))
    monkeypatch.setattr(bridge, "cleanup_request", lambda request_id: None)

    materials._finalize_distill(
        "request-book-0035", "book_0035",
        isolated / "06_工作区" / "SourcePrepare" / "book_0035_长安十二时辰",
        isolated / "02_素材知识库" / "book_0035_长安十二时辰",
    )
    assert looked_up == ["book_0035"]


def test_interactive_book_distill_rejects_missing_meta_asset_id(isolated, monkeypatch):
    from operations import qoder_bridge as bridge
    request_id = "request-missing-asset"
    monkeypatch.setattr(bridge, "get_request", lambda rid: {"state": "pending", "meta": {"sp_dir": "x", "bd_dir": "y"}})
    monkeypatch.setattr(bridge, "is_expired", lambda value: False)
    monkeypatch.setattr(bridge, "read_response", lambda rid: {"request_id": request_id, "status": "completed"})
    monkeypatch.setattr(bridge, "cleanup_request", lambda rid: None)
    result = materials.get_book_distill_request(request_id)
    assert result["status"] == "failed"
    assert "缺少素材标识" in result["error"]


# ---------------------------------------------------------------------------
# H. 页面加载零模型（隐式）+ REFERENCE_WORK 学习路径回归
# ---------------------------------------------------------------------------

def test_reference_work_learning_paths_uses_root_model_md(isolated):
    """REFERENCE_WORK 的 model.md 必须在 asset_dir 根，不在 bkp/ 子目录。"""
    asset_dir = isolated / "02_素材知识库" / "book_0001_样例作品"
    asset_dir.mkdir(parents=True)
    paths = materials._material_learning_paths("book_0001", "REFERENCE_WORK")
    assert len(paths) == 2
    assert paths[0].name == "author_view.md"
    assert paths[0].parent.name == "bkp"
    assert paths[1].name == "model.md"
    assert paths[1].parent.name == "book_0001_样例作品", "model.md 必须在 asset_dir 根，不在 bkp/"


def test_method_source_learning_paths(isolated):
    asset_dir = isolated / "02_素材知识库" / "book_0001_方法书"
    asset_dir.mkdir(parents=True)
    paths = materials._material_learning_paths("book_0001", "METHOD_SOURCE")
    assert len(paths) == 1
    assert paths[0].name == "method_profile.md"

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
    assert detail["state"] == "pending_distill"
    assert detail["workflow_stage"] == "purified"


# ---------------------------------------------------------------------------
# I. workflow_stage 派生（needs_attention 停留在失败前阶段，不改变所属阶段）
# ---------------------------------------------------------------------------

def _ref_asset(pur="可用", know="未开始", files=None):
    return {"id": "book_0001", "type": "REFERENCE_WORK", "author": "",
            "purification": {"status": pur}, "knowledge": {"status": know},
            "files": files if files is not None else [{"path": "x.epub"}]}


def test_workflow_stage_ready_is_writing(isolated, monkeypatch):
    monkeypatch.setattr(materials, "_bkp_acceptance_view", lambda a: "ready")
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda a: True)
    c = materials._classify_author_group(_ref_asset(pur="可用", know="可用"))
    assert c["state"] == "ready" and c["workflow_stage"] == "writing" and c["writing_callable"] is True


def test_workflow_stage_post_distill_acceptance_pending_stays_purified(isolated, monkeypatch):
    """Case A：knowledge=可用但 BKP 验收 pending → needs_attention，阶段停留 purified（不回落 new）。"""
    monkeypatch.setattr(materials, "_bkp_acceptance_view", lambda a: "pending")
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda a: True)
    c = materials._classify_author_group(_ref_asset(pur="可用", know="可用"))
    assert c["state"] == "needs_attention" and c["workflow_stage"] == "purified"


def test_workflow_stage_not_discoverable_stays_purified(isolated, monkeypatch):
    """Case A：knowledge=可用但 KnowledgeRetrieve 不可发现 → needs_attention，阶段停留 purified。"""
    monkeypatch.setattr(materials, "_bkp_acceptance_view", lambda a: None)
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda a: False)
    c = materials._classify_author_group(_ref_asset(pur="可用", know="可用"))
    assert c["state"] == "needs_attention" and c["workflow_stage"] == "purified"


def test_workflow_stage_book_0010_shape_is_purified(isolated):
    """book_0010 奥术神座真实形态：purification=可用, knowledge=未开始 → purified（待蒸馏）。"""
    c = materials._classify_author_group(_ref_asset(pur="可用", know="未开始"))
    assert c["state"] == "pending_distill" and c["workflow_stage"] == "purified"


def test_workflow_stage_purify_failure_stays_new(isolated):
    """Case B：提纯失败 → needs_attention，阶段停留 new（作者在此重新提纯）。"""
    c = materials._classify_author_group(_ref_asset(pur="失败", know="未开始"))
    assert c["state"] == "needs_attention" and c["workflow_stage"] == "new"


def test_workflow_stage_pending_prepare_is_new(isolated):
    c = materials._classify_author_group(_ref_asset(pur="未处理", know="未开始"))
    assert c["state"] == "pending_prepare" and c["workflow_stage"] == "new"


# ---------------------------------------------------------------------------
# J. CP4 学习投影读取优先级（新包 author_view → 旧包根 model.md → 都没有则空）
# ---------------------------------------------------------------------------

def test_learning_projection_prefers_bkp_author_view(isolated):
    asset_dir = isolated / "02_素材知识库" / "book_0001_样例作品"
    (asset_dir / "bkp").mkdir(parents=True)
    (asset_dir / "bkp" / "author_view.md").write_text("## 总览\n从 author_view 学习。\n", encoding="utf-8")
    (asset_dir / "model.md").write_text("## 总览\n从 model 学习。\n", encoding="utf-8")
    _summary, sections = materials._learning_projection({"id": "book_0001", "type": "REFERENCE_WORK"})
    bodies = " ".join(s["body"] for s in sections)
    assert "author_view" in bodies and "model" not in bodies, "新包必须优先读 bkp/author_view.md"


def test_learning_projection_falls_back_to_root_model(isolated):
    """旧包形态（book_0038/book_0065）：无 bkp/author_view.md，只有根 model.md → 正确显示 model。"""
    asset_dir = isolated / "02_素材知识库" / "book_0001_样例作品"
    (asset_dir / "bkp").mkdir(parents=True)
    (asset_dir / "model.md").write_text("## 总览\n从 model 学习。\n", encoding="utf-8")
    _summary, sections = materials._learning_projection({"id": "book_0001", "type": "REFERENCE_WORK"})
    assert sections and sections[0]["body"].strip() == "从 model 学习。"


def test_learning_projection_empty_when_no_source(isolated):
    """两者都无 → 空详情，绝不造假。"""
    asset_dir = isolated / "02_素材知识库" / "book_0001_样例作品"
    (asset_dir / "bkp").mkdir(parents=True)
    summary, sections = materials._learning_projection({"id": "book_0001", "type": "REFERENCE_WORK"})
    assert summary is None and sections == []
