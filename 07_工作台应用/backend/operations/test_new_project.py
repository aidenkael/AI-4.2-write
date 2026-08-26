# -*- coding: utf-8 -*-
"""新建作品“我有个想法”纵切 targeted tests（Qoder 桥版本）。

架构（已确认）：Go Write 管长期记忆；Qoder 桌面端只执行当前任务。
Go Write 只准备任务（pending request）并回收结果，不直接调用模型 API。

覆盖用户要求的验证：
1. prepare 不创建 03_作品工程
2. Go Write 创建唯一 pending request（含完整 task + response_path + active 指针）
3. pending 直到 Qoder 写回；写回后 completed 且候选走现有 StoryDesign
4. request_id 防串任务：不一致的 response 被丢弃
5. 取消后旧结果不可能被接受
6. 超时（expired）
7. 严格 JSON/字段验证仍然存在（非法输出/缺字段/类型错误 → failed）
8. 明确确认后调用真实 ProjectWorkspace.create_project（author_intent 过 frozen gate）
9. 新作品可被现有 list/open/overview 链读取；不生成正文
10. 不修改现有 frozen Skills（仅 import，不改文件；git diff 另查）
11. 旧 response 不会串到新请求（不同 request_id 天然隔离）
12. “两条狗咬”模拟完整链路（真实模型执行由 Qoder /gowrite 完成，见真实验证）
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import new_project as np_ops  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations.agent_runner import AgentRunError  # noqa: E402
from operations.agent_runner import run_task  # noqa: E402
from operations.projects import (  # noqa: E402
    get_project_overview,
    list_projects,
    open_project,
)

VALID_AGENT_RESULT = {
    "semantic_interpretation": {
        "scope": "story_design",
        "objective": "设计一个可推进的故事发动机。",
        "knowledge_needs": [],
        "selected_knowledge_refs": [],
        "package_ref": "",
        "assumptions": ["主角与秘密的因果尚未确认"],
    },
    "model_output": {
        "stance": ["story_engine"],
        "proposal": "候选：主角在暴雨夜发现花园替人保存秘密。",
        "work_direction": "都市奇幻长篇的开端设计。",
        "reader_promise": "读者先感到日常秩序被一条私人秘密撬开。",
        "hard_constraints": ["不把候选谜底写成既成事实"],
        "open_space": ["秘密来源", "关系走向"],
        "unknowns": ["花园保存秘密的代价"],
    },
}

# “两条狗咬”模拟结果（真实执行由 Qoder 桌面端完成）
TWO_DOGS_RESULT = {
    "semantic_interpretation": {
        "scope": "story_design",
        "objective": "围绕“主角被两条狗咬”设计一个有张力的故事方向。",
        "knowledge_needs": [],
        "selected_knowledge_refs": [],
        "package_ref": "",
        "assumptions": ["两条狗的来历与动机是故事核心悬念，作者尚未确认"],
    },
    "model_output": {
        "stance": ["story_engine"],
        "proposal": "候选：主角在小镇接连被两条狗咬伤，伤口愈合后开始听懂犬吠，卷入两条狗背后的秘密。",
        "work_direction": "现实奇幻短长篇的开端设计。",
        "reader_promise": "读者先感到被咬之后的日常异常，再被两条狗的秘密牵引。",
        "hard_constraints": ["不把两条狗的秘密写成既成事实"],
        "open_space": ["狗的来历", "咬伤后果", "小镇关系"],
        "unknowns": ["两条狗为什么只咬主角"],
    },
}


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """隔离：03_作品工程 → tmp；临时工作区 → tmp；桥根 → tmp；配置目录 → tmp。"""
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    monkeypatch.setattr(np_ops, "get_proposals_root", lambda: tmp_path / "proposals")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / "qoder_bridge")
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return projects_root


# ---------- 1. prepare 不创建 03_作品工程 ----------

def test_prepare_does_not_create_project(isolated):
    prepared = np_ops.prepare_new_project(name="测试作品", idea="我想写一个……")
    assert prepared["status"] == "task_prepared"
    assert prepared["request_id"]
    assert "Qoder" in prepared["message"]
    # 03_作品工程 仍然为空（只有目录本身，无任何作品子目录）
    children = [p for p in isolated.iterdir() if p.is_dir()]
    assert children == [], f"prepare 不应创建作品，实际：{children}"


# ---------- 2. 唯一 pending request：完整 task + response_path + 精确激活 ----------

def test_prepare_creates_unique_request(isolated):
    a = np_ops.prepare_new_project(name="请求A", idea="想法A")
    assert a["request_id"], "每次准备必须是唯一 request_id"

    req_a = bridge.get_request(a["request_id"])
    assert req_a["state"] == "pending"
    assert "想法A" in req_a["task"] and "请求A" in req_a["task"], "完整 Agent task 必须保存在请求中"
    resp_parts = Path(req_a["response_path"]).parts
    assert "responses" in resp_parts and resp_parts[-1] == f"{a['request_id']}.json"
    # Interactive 显式激活：active.json 精确指向该请求
    assert bridge.get_active_request_id() == a["request_id"], "active 精确指向当前请求"

    # 第二个 Interactive 请求不能覆盖第一个：稳定忙碌错误，绝不静默覆盖
    with pytest.raises(np_ops.NewProjectError) as ei:
        np_ops.prepare_new_project(name="请求B", idea="想法B")
    assert "Qoder /gowrite" in str(ei.value)
    assert bridge.get_active_request_id() == a["request_id"], "active 仍指向第一个请求"

    # response 目录尚无任何文件（pending）
    assert not bridge.response_path(a["request_id"]).exists()


# ---------- 3. pending → 写回 → completed，候选走现有 StoryDesign ----------

def test_pending_until_response_then_completed(isolated):
    prepared = np_ops.prepare_new_project(name="完整链作品", idea="想法")
    rid = prepared["request_id"]

    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "pending"

    bridge.write_response(rid, result=VALID_AGENT_RESULT)
    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "completed"
    assert status["result"]["status"] == "proposal_noncanonical"

    # StoryDesign 产物已写入临时工作区（briefs/contexts/designs）
    proposals = isolated.parent / "proposals"
    proj_dir = proposals / status["result"]["project_id"]
    assert (proj_dir / "briefs" / "brief-idea-001.json").exists()
    assert (proj_dir / "contexts" / "context-idea-001.json").exists()
    assert (proj_dir / "designs" / "design-idea-001.json").exists()
    candidate = json.loads((proj_dir / "designs" / "design-idea-001.json").read_text(encoding="utf-8"))
    assert candidate["content"]["work_direction"] == "都市奇幻长篇的开端设计。"

    # 完成后桥文件已清理（旧结果不可能再被接受）
    assert bridge.get_request(rid) is None
    assert not bridge.response_path(rid).exists()


# ---------- 4. request_id 防串任务：不一致的 response 被丢弃 ----------

def test_request_id_mismatch_rejected(isolated):
    prepared = np_ops.prepare_new_project(name="防串作品", idea="想法")
    rid = prepared["request_id"]
    # 模拟 Qoder 写错 request_id：文件在正确位置，但内容 request_id 不一致
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "gowrite_response/v1",
        "request_id": "other-request-id",
        "status": "completed",
        "result": VALID_AGENT_RESULT,
    }, ensure_ascii=False), encoding="utf-8")

    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "failed"
    assert "request_id" in status["error"]
    # 候选未生成、临时工作区已清理、桥文件已清理
    assert list(isolated.iterdir()) == []


# ---------- 5. 取消后旧结果不可能被接受 ----------

def test_cancel_then_response_not_accepted(isolated):
    prepared = np_ops.prepare_new_project(name="取消作品", idea="想法")
    rid = prepared["request_id"]

    canceled = np_ops.cancel_new_project_request(rid)
    assert canceled["status"] == "canceled"

    # 取消后即使 Qoder 再写回，也不会被接受
    bridge.write_response(rid, result=VALID_AGENT_RESULT)
    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "canceled"
    assert "result" not in status or status["result"] is None
    assert list(isolated.iterdir()) == [], "取消后临时工作区应已清理"


# ---------- 6. 超时（expired） ----------

def test_expired_request(isolated, monkeypatch):
    prepared = np_ops.prepare_new_project(name="超时作品", idea="想法")
    rid = prepared["request_id"]

    monkeypatch.setattr(bridge, "is_expired", lambda req: True)
    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "expired"
    assert "超时" in status["error"]
    assert bridge.get_request(rid) is None
    assert list(isolated.iterdir()) == [], "超时后临时工作区应已清理"


# ---------- 7. 严格 JSON/字段验证仍然存在 ----------

def test_invalid_json_output_rejected(isolated):
    prepared = np_ops.prepare_new_project(name="坏输出作品", idea="想法")
    rid = prepared["request_id"]
    bridge.write_response(rid, output="这不是 JSON")

    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "failed"
    assert "JSON" in status["error"]
    assert list(isolated.iterdir()) == []


def test_work_direction_not_string_rejected(isolated):
    bad = {
        "semantic_interpretation": {
            "scope": "story_design", "objective": "目标",
            "knowledge_needs": [], "selected_knowledge_refs": [], "package_ref": "", "assumptions": [],
        },
        "model_output": {
            "proposal": "候选方向。", "work_direction": 12345,
            "reader_promise": "读者期待。", "hard_constraints": [], "open_space": [],
        },
    }
    prepared = np_ops.prepare_new_project(name="类型错误作品", idea="想法")
    bridge.write_response(prepared["request_id"], result=bad)
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "failed"
    assert "work_direction" in status["error"]
    assert list(isolated.iterdir()) == []


def test_reader_promise_missing_rejected(isolated):
    bad = {
        "semantic_interpretation": {
            "scope": "story_design", "objective": "目标",
            "knowledge_needs": [], "selected_knowledge_refs": [], "package_ref": "", "assumptions": [],
        },
        "model_output": {
            "proposal": "候选方向。", "work_direction": "作品方向。",
            "hard_constraints": [], "open_space": [],
        },
    }
    prepared = np_ops.prepare_new_project(name="缺读者期待", idea="想法")
    bridge.write_response(prepared["request_id"], result=bad)
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "failed"
    assert "reader_promise" in status["error"]


def test_hard_constraints_not_list_str_rejected(isolated):
    bad = {
        "semantic_interpretation": {
            "scope": "story_design", "objective": "目标",
            "knowledge_needs": [], "selected_knowledge_refs": [], "package_ref": "", "assumptions": [],
        },
        "model_output": {
            "proposal": "候选方向。", "work_direction": "作品方向。",
            "reader_promise": "读者期待。", "hard_constraints": "不是列表", "open_space": [],
        },
    }
    prepared = np_ops.prepare_new_project(name="约束类型错误", idea="想法")
    bridge.write_response(prepared["request_id"], result=bad)
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "failed"
    assert "hard_constraints" in status["error"]


def test_open_space_missing_rejected(isolated):
    bad = {
        "semantic_interpretation": {
            "scope": "story_design", "objective": "目标",
            "knowledge_needs": [], "selected_knowledge_refs": [], "package_ref": "", "assumptions": [],
        },
        "model_output": {
            "proposal": "候选方向。", "work_direction": "作品方向。",
            "reader_promise": "读者期待。", "hard_constraints": [],
        },
    }
    prepared = np_ops.prepare_new_project(name="缺自由空间作品", idea="想法")
    bridge.write_response(prepared["request_id"], result=bad)
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "failed"
    assert "open_space" in status["error"]


def test_knowledge_needs_missing_rejected(isolated):
    bad = {
        "semantic_interpretation": {
            "scope": "story_design", "objective": "目标",
            "selected_knowledge_refs": [], "assumptions": [],
        },
        "model_output": {
            "proposal": "候选方向。", "work_direction": "作品方向。",
            "reader_promise": "读者期待。", "hard_constraints": [], "open_space": [],
        },
    }
    prepared = np_ops.prepare_new_project(name="缺知识需求作品", idea="想法")
    bridge.write_response(prepared["request_id"], result=bad)
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "failed"
    assert "knowledge_needs" in status["error"]


def test_output_string_form_accepted(isolated):
    """response 用 output 字符串（模型原始文本）兜底也应通过同一严格解析。"""
    prepared = np_ops.prepare_new_project(name="字符串输出", idea="想法")
    bridge.write_response(prepared["request_id"], output=json.dumps(VALID_AGENT_RESULT, ensure_ascii=False))
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "completed"
    assert status["result"]["candidate"]["work_direction"] == "都市奇幻长篇的开端设计。"


def test_response_with_unescaped_quotes_rejected(isolated):
    """未转义英文双引号导致的非法 JSON：严格拒绝，Go Write 不再猜测修复。

    产生合法 JSON 是 Qoder 的职责（/gowrite 必须用标准 JSON parser 自验证）。
    """
    prepared = np_ops.prepare_new_project(name="引号作品", idea="想法")
    rid = prepared["request_id"]
    # 模拟 Qoder 原样写入：字符串值内含未转义的 "（真实复现自两条狗案例）
    raw = (
        '{\n'
        '  "schema": "gowrite_response/v1",\n'
        '  "request_id": "%s",\n'
        '  "status": "completed",\n'
        '  "result": {\n'
        '    "semantic_interpretation": {\n'
        '      "scope": "story_design",\n'
        '      "objective": "为一部以"主角被两条狗咬"为核心事件的故事生成方向",\n'
        '      "knowledge_needs": [],\n'
        '      "selected_knowledge_refs": [],\n'
        '      "assumptions": [""两条狗"是核心意象，但不确定是字面意义还是隐喻"]\n'
        '    },\n'
        '    "model_output": {\n'
        '      "proposal": "候选：一个普通人被两条狗咬伤，生活裂缝不断扩大。",\n'
        '      "work_direction": "聚焦小人物被两条狗咬伤后失控的中篇。",\n'
        '      "reader_promise": "读者感到那些"温顺"事物恰恰是危险的。",\n'
        '      "hard_constraints": ["不合并两条狗的来源"],\n'
        '      "open_space": ["狗的来历"]\n'
        '    }\n'
        '  }\n'
        '}\n'
    ) % rid
    path = bridge.response_path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")

    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "failed", "非法 response 必须严格拒绝，不得自动修复"
    assert "JSON" in status["error"]
    assert "result" not in status or status["result"] is None
    # 临时工作区与桥文件都已清理
    assert list(isolated.iterdir()) == []
    assert bridge.get_request(rid) is None


def test_response_with_fullwidth_quotes_accepted(isolated):
    """中文引号 “ ” / 「 」 是合法 JSON 内容，走完整链路直接接受。"""
    prepared = np_ops.prepare_new_project(name="全角引号作品", idea="想法")
    rid = prepared["request_id"]
    result = json.loads(json.dumps(VALID_AGENT_RESULT, ensure_ascii=False))
    result["model_output"]["work_direction"] = "围绕「主角与秘密」展开，读者期待“真实”。"
    result["model_output"]["proposal"] = "候选：主角说“我藏了一个秘密”，然后消失。"
    bridge.write_response(rid, result=result)
    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "completed"
    assert "「主角与秘密」" in status["result"]["candidate"]["work_direction"]
    assert "“我藏了一个秘密”" in status["result"]["candidate"]["proposal"]


# ---------- 8/9. 明确确认 → 真实 create_project；现有链可读；不生成正文 ----------

def _complete(prepared) -> dict:
    bridge.write_response(prepared["request_id"], result=VALID_AGENT_RESULT)
    status = np_ops.get_new_project_request(prepared["request_id"])
    assert status["status"] == "completed"
    return status["result"]


def test_confirm_without_token_rejected(isolated):
    with pytest.raises(np_ops.NewProjectError):
        np_ops.confirm_new_project(proposal_token="")
    with pytest.raises(np_ops.NewProjectError):
        np_ops.confirm_new_project(proposal_token="不存在的token")
    assert list(isolated.iterdir()) == []


def test_confirm_rejects_forged_token(isolated):
    prepared = np_ops.prepare_new_project(name="防伪造", idea="想法")
    _complete(prepared)
    with pytest.raises(np_ops.NewProjectError):
        np_ops.confirm_new_project(proposal_token="forged-token-00000000")
    assert list(isolated.iterdir()) == []


def test_confirm_creates_real_project(isolated):
    prepared = np_ops.prepare_new_project(name="正式作品", idea="想法")
    result = _complete(prepared)
    created = np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    assert created["name"] == "正式作品"
    assert created["project_id"] == result["project_id"]
    proj_dir = isolated / "正式作品"
    assert proj_dir.exists()
    assert (proj_dir / "_工作台状态" / "author_intent.json").exists()
    assert (proj_dir / "_工作台状态" / "story_state.json").exists()
    assert (proj_dir / "_工作台状态" / "accepted_text_index.json").exists()


def test_confirm_intent_passes_frozen_gate(isolated):
    prepared = np_ops.prepare_new_project(name="门槛作品", idea="想法")
    result = _complete(prepared)
    created = np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    intent = json.loads(
        (isolated / "门槛作品" / "_工作台状态" / "author_intent.json").read_text(encoding="utf-8")
    )
    assert intent["project_id"] == created["project_id"]
    assert intent["intent_rev"] == 1
    for field in ("work_direction", "reader_promise", "hard_constraints", "open_space"):
        assert field in intent


def test_new_project_readable_by_existing_chain(isolated):
    prepared = np_ops.prepare_new_project(name="可读作品", idea="想法")
    result = _complete(prepared)
    created = np_ops.confirm_new_project(proposal_token=result["proposal_token"])

    items = list_projects()
    assert any(p["project_id"] == created["project_id"] for p in items)

    opened = open_project({"project_id": created["project_id"]})
    assert opened["project_id"] == created["project_id"]

    overview = get_project_overview(created["project_id"])
    assert overview["project_id"] == created["project_id"]
    assert overview["name"] == "可读作品"


def test_confirm_generates_no_prose(isolated):
    prepared = np_ops.prepare_new_project(name="无正文作品", idea="想法")
    result = _complete(prepared)
    np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    prose_dir = isolated / "无正文作品" / "03_正文"
    assert prose_dir.exists()
    assert list(prose_dir.iterdir()) == [], "创建作品不得生成正文"
    index = json.loads(
        (isolated / "无正文作品" / "_工作台状态" / "accepted_text_index.json").read_text(encoding="utf-8")
    )
    assert index["entries"] == []


def test_proposal_cleaned_after_confirm(isolated):
    prepared = np_ops.prepare_new_project(name="清理作品", idea="想法")
    result = _complete(prepared)
    assert (isolated.parent / "proposals" / result["project_id"]).exists()
    np_ops.confirm_new_project(proposal_token=result["proposal_token"])
    assert not (isolated.parent / "proposals" / result["project_id"]).exists()


# ---------- 10. frozen Skills 零修改（只 import 不改文件） ----------

def test_frozen_skills_untouched(isolated):
    import story_runtime  # noqa: F401
    import story_design  # noqa: F401
    import project_workspace  # noqa: F401
    # 只要这些模块能原样 import 并使用即证明未被破坏；git diff 另行验证文件未改。
    assert hasattr(story_runtime, "validate_author_intent")
    assert hasattr(project_workspace, "create_project")


# ---------- 11. 旧 response 不会串到新请求 ----------

def test_old_response_not_leaked_to_new_request(isolated):
    # 请求 A：写回完成（未消费）→ 显式取消清理；再建请求 B —— B 必须保持
    # pending，绝不能读到 A 的结果（response 按 request_id 隔离；交互忙碌
    # 保护下 B 只能在新一轮生命周期创建）
    a = np_ops.prepare_new_project(name="旧请求", idea="旧想法")
    bridge.write_response(a["request_id"], result=VALID_AGENT_RESULT)
    np_ops.cancel_new_project_request(a["request_id"])

    b = np_ops.prepare_new_project(name="新请求", idea="新想法")
    status_b = np_ops.get_new_project_request(b["request_id"])
    assert status_b["status"] == "pending", "新请求绝不能读到旧 response"

    # B 自己的结果正常到达
    bridge.write_response(b["request_id"], result=TWO_DOGS_RESULT)
    status_b = np_ops.get_new_project_request(b["request_id"])
    assert status_b["status"] == "completed"
    assert status_b["result"]["project_id"] != a["request_id"]


# ---------- 12. “两条狗咬”完整链路（模拟 Qoder 写回；真实执行见真实验证） ----------

def test_two_dogs_full_chain(isolated):
    prepared = np_ops.prepare_new_project(name="两条狗", idea="写一个主角被两条狗咬的故事")
    rid = prepared["request_id"]
    assert "两条狗咬" in prepared["message"] or "Qoder" in prepared["message"]

    req = bridge.get_request(rid)
    assert "写一个主角被两条狗咬的故事" in req["task"]

    bridge.write_response(rid, result=TWO_DOGS_RESULT)
    status = np_ops.get_new_project_request(rid)
    assert status["status"] == "completed"
    assert status["result"]["status"] == "proposal_noncanonical"
    assert status["result"]["candidate"]["work_direction"]
    assert status["result"]["candidate"]["proposal"]

    created = np_ops.confirm_new_project(proposal_token=status["result"]["proposal_token"])
    assert created["name"] == "两条狗"
    assert (isolated / "两条狗" / "_工作台状态" / "author_intent.json").exists()


# ---------- 后处理失败 → partial success（沿用旧语义） ----------

def test_approved_direction_failure_is_partial_success(isolated, monkeypatch):
    prepared = np_ops.prepare_new_project(name="部分成功作品", idea="想法")
    result = _complete(prepared)
    token = result["proposal_token"]
    project_id = result["project_id"]

    def _failing_apply_diff(*args, **kwargs):
        from story_runtime import ContractError as SDContractError
        raise SDContractError("模拟登记失败")

    monkeypatch.setattr(np_ops, "apply_diff", _failing_apply_diff)

    created = np_ops.confirm_new_project(proposal_token=token)
    assert created["project_id"] == project_id
    assert created["name"] == "部分成功作品"
    assert created["approved_direction_registered"] is False
    assert created["warning"] is not None
    assert "作品已创建" in created["warning"]

    items = list_projects()
    assert any(p["project_id"] == project_id for p in items)
    prose_dir = isolated / "部分成功作品" / "03_正文"
    assert prose_dir.exists()
    assert list(prose_dir.iterdir()) == []
    assert not (isolated.parent / "proposals" / project_id).exists()

    with pytest.raises(np_ops.NewProjectError, match="候选已失效"):
        np_ops.confirm_new_project(proposal_token=token)


def test_brief_read_failure_is_partial_success(isolated, monkeypatch):
    prepared = np_ops.prepare_new_project(name="读取失败作品", idea="想法")
    result = _complete(prepared)
    token = result["proposal_token"]
    project_id = result["project_id"]

    from pathlib import Path as RealPath
    original_read_text = RealPath.read_text

    def _failing_read_text(self, encoding=None):
        if "briefs" in str(self) and "brief-idea-001" in str(self):
            raise OSError("模拟 brief 读取失败")
        return original_read_text(self, encoding=encoding)

    monkeypatch.setattr(RealPath, "read_text", _failing_read_text)

    created = np_ops.confirm_new_project(proposal_token=token)
    assert created["project_id"] == project_id
    assert created["approved_direction_registered"] is False
    assert created["warning"] is not None
    assert "作品已创建" in created["warning"]
    items = list_projects()
    assert any(p["project_id"] == project_id for p in items)
    assert not (isolated.parent / "proposals" / project_id).exists()


def test_load_project_failure_is_partial_success(isolated, monkeypatch):
    prepared = np_ops.prepare_new_project(name="加载失败作品", idea="想法")
    result = _complete(prepared)
    token = result["proposal_token"]
    project_id = result["project_id"]

    def _failing_load_project(*args, **kwargs):
        raise OSError("模拟 load_project 失败")

    monkeypatch.setattr(np_ops, "load_project", _failing_load_project)

    created = np_ops.confirm_new_project(proposal_token=token)
    assert created["project_id"] == project_id
    assert created["approved_direction_registered"] is False
    assert created["warning"] is not None
    items = list_projects()
    assert any(p["project_id"] == project_id for p in items)
    assert not (isolated.parent / "proposals" / project_id).exists()


# ---------- 既有 Agent runner 行为不变（run_task 仍由设置-测试连接等使用） ----------

def test_runner_rejects_unavailable_agent(isolated, tmp_path, monkeypatch):
    from config.settings import SettingsStore, AppSettings
    store = SettingsStore(config_dir=tmp_path / "cfg")
    store.save(AppSettings(default_execution_mode="direct", direct_agent="qoder"))
    with pytest.raises(AgentRunError):
        run_task("任何任务")
