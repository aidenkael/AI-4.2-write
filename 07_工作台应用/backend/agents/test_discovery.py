import json

from agents.deepseek_harness import (
    DeepSeekHarnessAdapter,
    _effective_headless_model,
    _model_selection_kind,
    _provider_models,
    _selection_from_custom,
)
from agents import qoder
from agents.qoder import QoderAdapter


def test_qoder_desktop_command_definition_and_authoritative_path(tmp_path, monkeypatch):
    targets = [
        tmp_path / ".qoder" / "commands" / "gowrite.md",
        tmp_path / ".qoder-cn" / "commands" / "gowrite.md",
    ]
    monkeypatch.setattr(qoder, "_command_paths", lambda: targets)

    result = qoder.install_command()

    assert result["status"] == "installed"
    assert len(result["installed_paths"]) == 2
    assert result["command_ready"] is True
    for target in targets:
        assert target.read_text(encoding="utf-8") == qoder.command_definition()
    assert qoder.command_definition().startswith("---\ndescription: ")
    assert "type:" not in qoder.command_definition()


def test_qoder_command_ready_validates_any_supported_location(tmp_path, monkeypatch):
    """就绪状态按真实位置+内容校验：任一受支持位置内容精确匹配即为就绪。"""
    cn_target = tmp_path / ".qoder-cn" / "commands" / "gowrite.md"
    qoder_target = tmp_path / ".qoder" / "commands" / "gowrite.md"
    monkeypatch.setattr(qoder, "_command_paths", lambda: [qoder_target, cn_target])

    # 只有一个位置存在且内容不符 → 未就绪
    qoder_target.parent.mkdir(parents=True)
    qoder_target.write_text("stale content", encoding="utf-8")
    assert qoder.command_ready() is False
    # 一个位置内容精确匹配 → 就绪
    qoder_target.write_text(qoder.command_definition(), encoding="utf-8")
    assert qoder.command_ready() is True


def test_qoder_install_reports_write_failure(tmp_path, monkeypatch):
    blocked_parent = tmp_path / ".qoder" / "commands"
    blocked_parent.parent.mkdir()
    blocked_parent.write_text("not a directory", encoding="utf-8")
    target = blocked_parent / "gowrite.md"
    monkeypatch.setattr(qoder, "_command_paths", lambda: [target])

    result = qoder.install_command()

    assert result["status"] == "error"
    assert result["command_ready"] is False
    assert result["installed_paths"] == []
    assert result["errors"]


def test_qoder_discovery_keeps_desktop_and_cli_separate(monkeypatch):
    monkeypatch.setattr("agents.qoder._discover_desktop", lambda: {"installed": True, "status": "installed", "path": "desktop", "launcher_path": "desktop", "version": "1.24.2", "error": None})
    monkeypatch.setattr("agents.qoder._default_cli", lambda: "qoderclicn")
    def run(cmd, **_):
        if "--version" in cmd: return type("R", (), {"returncode": 0, "stdout": "1.1.28\n", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "MODEL\nactual\n", "stderr": ""})()
    monkeypatch.setattr("agents.qoder.subprocess.run", run)
    env = QoderAdapter.discover()
    assert env["desktop"]["version"] == "1.24.2"
    assert env["cli"]["kind"] == "qoder_cn"
    assert env["direct"]["models"][0]["id"] == "actual"
    assert env["direct"]["custom_models"] == []


def test_qoder_discovery_splits_custom_route_from_catalog(monkeypatch):
    """v1.1.29 真实目录形状：自定义路由 `(Provider) (provider/model)` 单独分组，
    其 id 是可调用的 modelID；内置模型保留原名。"""
    monkeypatch.setattr("agents.qoder._discover_desktop", lambda: {"installed": True, "status": "installed", "path": "desktop", "launcher_path": "desktop", "version": "1.1.29", "error": None})
    monkeypatch.setattr("agents.qoder._default_cli", lambda: "qoderclicn")
    def run(cmd, **_):
        if "--version" in cmd: return type("R", (), {"returncode": 0, "stdout": "1.1.29\n", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "MODEL\nDeepSeek-V4-Pro\nQwen-3.8-Max (QwenCloud-China) (qwencloud-cn/qwen3.8-max-tp)\n", "stderr": ""})()
    monkeypatch.setattr("agents.qoder.subprocess.run", run)

    env = QoderAdapter.discover()
    natives = env["direct"]["models"]
    customs = env["direct"]["custom_models"]
    assert [m["id"] for m in natives] == ["DeepSeek-V4-Pro"]
    assert natives[0]["source"] == "native"
    assert len(customs) == 1
    assert customs[0]["id"] == "qwencloud-cn/qwen3.8-max-tp"
    assert customs[0]["source"] == "custom"
    assert customs[0]["selectable"] is True


def test_harness_discovery_unavailable(monkeypatch):
    monkeypatch.setattr("agents.deepseek_harness._default_launch", lambda: (_ for _ in ()).throw(RuntimeError("missing")))
    assert DeepSeekHarnessAdapter.discover()["installed"] is False


def test_harness_effective_model_comes_from_composed_plugin_block():
    dump = "- id: agent-default-model\n  name: '@deepseek-ai/dsh-agent-default-model'\n  config:\n    provider: local\n    model: actual-model\n- id: next\n"
    assert _effective_headless_model(dump) == ("local", "actual-model")
    assert _effective_headless_model("- id: agent-default-model\n  config: {}\n") == (None, None)


def test_harness_model_selection_is_truthful():
    """DeepSeek 可选手目录语义：
    - 只有受管默认（profile 单模型）→ managed，不伪造可选手；
    - 存在可选自定义路由（如 DeepSeek V4 Pro 经 pi-ai provider 配置）→ selectable；
    - 都没有 → none。"""
    managed_default = [{"id": "deepseek-v4-flash", "selectable": True}]
    custom_pro = [{"id": "harness:qwen-token-plan-cn:deepseek-v4-pro", "selectable": True}]
    assert _model_selection_kind(managed_default, []) == "managed"
    assert _model_selection_kind(managed_default, custom_pro) == "selectable"
    assert _model_selection_kind([], []) == "none"
    assert _model_selection_kind([], [{"id": "x", "selectable": False}]) == "none"


def test_harness_custom_routes_keep_provider_identity():
    routes = [
        {"provider": "token-plan", "model": "same", "credentialConfigured": True},
        {"provider": "api-billing", "model": "same", "credentialConfigured": True},
    ]
    assert _selection_from_custom("harness:token-plan:same", routes) == ("token-plan", "same")
    assert _selection_from_custom("harness:api-billing:same", routes) == ("api-billing", "same")


def test_harness_provider_models_groups_by_provider_no_hardcoding():
    """通用多 provider 解析：按 provider 分组、保留精确 id、去重、绝不硬编码。"""
    snapshot = {
        "routes": [
            {"provider": "deepseek", "model": "flash", "name": "DeepSeek V4 Flash", "credentialConfigured": True},
            {"provider": "deepseek", "model": "pro", "name": "DeepSeek V4 Pro", "credentialConfigured": True},
            {"provider": "deepseek", "model": "pro", "name": "DeepSeek V4 Pro dup", "credentialConfigured": True},
            {"provider": "qwen-token-plan-cn", "model": "qwen3.7-max", "name": "Qwen3.7 Max", "credentialConfigured": True},
            {"provider": "qwen-token-plan-cn", "model": "no-cred", "name": "No Cred", "credentialConfigured": False},
        ],
    }
    groups = _provider_models(snapshot)
    ids = [g["provider_id"] for g in groups]
    assert ids == ["deepseek", "qwen-token-plan-cn"], "多个 provider 都必须出现，不因某个成功而消失"
    deepseek = groups[0]
    assert [m["model_id"] for m in deepseek["models"]] == ["flash", "pro"], "精确重复路由只保留一次"
    assert deepseek["models"][1]["display_name"] == "DeepSeek V4 Pro"
    qwen = groups[1]
    assert [m["model_id"] for m in qwen["models"]] == ["qwen3.7-max", "no-cred"]
    assert qwen["models"][1]["selectable"] is False, "无凭据路由必须标不可选而非假装可用"
    selectable_groups = _provider_models(snapshot, selectable_only=True)
    assert [m["model_id"] for m in selectable_groups[1]["models"]] == ["qwen3.7-max"]
    # 精确 id 保持可执行路由格式
    assert deepseek["models"][0]["id"] == "harness:deepseek:flash"


def test_harness_discover_exposes_provider_models(monkeypatch, tmp_path):
    """discover 输出包含 provider_models（分组）与 managed_model（受管默认）。"""
    from agents import deepseek_harness as dh
    launch = ["node", "bin.js"]

    def fake_run(cmd, **_):
        if "--dump-config" in cmd:
            return type("R", (), {
                "returncode": 0,
                "stdout": "- id: agent-default-model\n  config:\n    provider: deepseek-official\n    model: deepseek-v4-flash\n",
                "stderr": "",
            })()
        if "-e" in cmd:  # settings 快照解析
            return type("R", (), {"returncode": 0, "stdout": json.dumps({
                "routes": [
                    {"provider": "qwen-token-plan-cn", "model": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "credentialConfigured": True},
                    {"provider": "qwen-token-plan-cn", "model": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "credentialConfigured": True},
                ],
                "providers": [],
                "default": {},
            }), "stderr": ""})()
        if "--version" in cmd:
            return type("R", (), {"returncode": 0, "stdout": "0.1.0-rc.6\n", "stderr": ""})()
        raise AssertionError(f"unexpected cmd {cmd}")

    monkeypatch.setattr(dh, "_default_launch", lambda: launch)
    monkeypatch.setattr(dh.subprocess, "run", fake_run)
    monkeypatch.setattr(dh, "_LOCAL_DSH_BIN", tmp_path / "none")
    env = DeepSeekHarnessAdapter.discover()
    direct = env["direct"]
    assert direct["model_selection"] == "selectable"
    assert direct["managed_model"]["id"] == "deepseek-v4-flash"
    assert direct["managed_model"]["provider_id"] == "deepseek-official"
    assert [g["provider_id"] for g in direct["provider_models"]] == ["qwen-token-plan-cn"]
    pro = next(m for m in direct["provider_models"][0]["models"] if m["model_id"] == "deepseek-v4-pro")
    assert pro["id"] == "harness:qwen-token-plan-cn:deepseek-v4-pro"
    assert pro["selectable"] is True
    # 扁平 custom_models 与 provider_models 一致（向后兼容）
    assert len(direct["custom_models"]) == 2
