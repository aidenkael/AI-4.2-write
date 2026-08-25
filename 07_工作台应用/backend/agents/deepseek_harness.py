# -*- coding: utf-8 -*-
"""DeepSeek Harness headless Adapter（薄胶水）。

直接复用本机已安装 DeepSeek Harness 的原始运行方式（已实测可用）：

    node <dsh>/lib/bin.js --profile headless "<task>"

职责边界（只做薄胶水，不扩建平台）：
- 只负责：subprocess 启动、cwd 传入、任务传入、stdout 作为最终结果、
  stderr / 非 0 退出码 → failed、可终止当前子进程 → cancelled。
- 不复制 Harness 的 Agent loop / 工具 / 权限 / 模型 / Skill / session 等内部能力；
- 不自行实现它当前没有的 stream / resume / model CLI 功能（能力表如实声明）。
- 不修改 DeepSeek Harness；不把 E:\\DeepSeek Harness 业务逻辑硬编码到
  Author Operations。启动位置作为配置传入（launch 参数 / 环境变量 DSH_BIN /
  PATH 上的 dsh / 本机已验证的默认安装位），后续由设置页正式配置。
"""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import threading
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from agents.base import AgentAdapter, AgentRequest, AgentResult

# 本机已验证可用的默认安装位（仅作回退默认；优先：launch 参数 → DSH_BIN → PATH dsh）
_LOCAL_DSH_BIN = Path(r"E:\DeepSeek Harness\node_modules\@deepseek-ai\dsh\lib\bin.js")


def _harness_package_root(launch: list[str]) -> Optional[str]:
    """Resolve the Harness package root (nearest ancestor containing node_modules).

    ``bin.js`` lives at ``<root>/node_modules/@deepseek-ai/dsh/lib/bin.js``.
    Falls back to None when the launch is not a real filesystem path (tests) —
    the ``node -e`` yaml import then resolves from the process cwd.
    """
    if len(launch) < 2:
        return None
    try:
        candidate = Path(launch[-1]).resolve()
    except OSError:
        return None
    for parent in [candidate, *candidate.parents]:
        if (parent / "node_modules").is_dir():
            return str(parent)
    return None


def _harness_config_snapshot(launch: list[str], dsh_home: Path) -> dict:
    """Read only non-secret route metadata from the Harness YAML documents.

    Generic provider discovery: enumerates every configured ``llm-pi-ai``
    provider and every model under it. A malformed provider must never hide
    another provider's routes (per-provider isolation). Only route/model ids
    and credential *names* are projected; credential values never leave the
    credentials file.
    """
    settings = dsh_home / "settings.yaml"
    credentials = dsh_home / ".credentials.yaml"
    if not settings.is_file():
        return {"routes": [], "default": {}, "providers": []}
    # Use Harness's own YAML dependency; the script deliberately projects only
    # route/model ids and credential *names*, never credential values.
    code = """
import fs from 'node:fs'; import YAML from 'yaml';
const settings = YAML.parse(fs.readFileSync(process.argv[1], 'utf8')) || {};
const credentials = fs.existsSync(process.argv[2]) ? (YAML.parse(fs.readFileSync(process.argv[2], 'utf8')) || {}) : {};
const refs = new Set(Object.keys(credentials));
const providers = settings['llm-pi-ai']?.providers || {};
const providersOut = Object.entries(providers).map(([provider, profile]) => {
  const models = Array.isArray(profile?.models) ? profile.models : [];
  const apiKeyEnv = typeof profile?.apiKeyEnv === 'string' ? profile.apiKeyEnv : null;
  const credentialConfigured = !apiKeyEnv || refs.has(apiKeyEnv);
  return {
    provider,
    apiKeyEnv,
    credentialConfigured,
    models: models
      .map((model) => ({
        model: String(model?.id || ''),
        name: typeof model?.name === 'string' ? model.name : null,
      }))
      .filter((entry) => entry.model),
  };
}).filter((p) => p.models.length > 0);
const routes = providersOut.flatMap((p) =>
  p.models.map((m) => ({
    provider: p.provider, model: m.model, name: m.name,
    credentialConfigured: p.credentialConfigured,
  })),
);
console.log(JSON.stringify({routes, providers: providersOut, default: settings['agent-default-model'] || {}}));
"""
    root = _harness_package_root(launch)
    result = subprocess.run(
        [launch[0], "--input-type=module", "-e", code, str(settings), str(credentials)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12, cwd=root,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Harness 设置解析失败")
    return json.loads(result.stdout)


def _custom_id(provider: str, model: str) -> str:
    return f"harness:{provider}:{model}"


def _model_selection_kind(native_models: list, custom_models: list) -> str:
    """真话语义（供 discover 使用，纯函数便于 fixture 测试）：

    - 存在可选自定义路由 → ``selectable``（可选手 = 受管默认 + 自定义路由）；
    - 只有受管默认模型（profile 配置）→ ``managed``；
    - 都没有 → ``none``。
    绝不因为只有一个受管模型就伪造可选手目录。
    """
    if any(item.get("selectable") for item in custom_models):
        return "selectable"
    if native_models:
        return "managed"
    return "none"


def _selection_from_custom(custom_model: str, routes: list[dict]) -> tuple[str, str]:
    for route in routes:
        if _custom_id(str(route["provider"]), str(route["model"])) == custom_model and route.get("credentialConfigured"):
            return str(route["provider"]), str(route["model"])
    raise RuntimeError("所选 Harness 自定义模型路由当前不可用")


def _provider_models(snapshot: dict, *, selectable_only: bool = False) -> list[dict]:
    """Generic provider-grouped route catalog (no provider-specific names).

    - enumerates every configured provider and every model under it;
    - preserves exact provider id + model id (id = ``harness:<provider>:<model>``);
    - keeps display names separate from callable ids;
    - de-duplicates exact duplicate (provider, model) routes only.
    ``selectable_only=True`` drops routes whose credential is not configured.
    """
    grouped: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for route in snapshot.get("routes", []):
        provider = str(route.get("provider") or "")
        model = str(route.get("model") or "")
        if not provider or not model:
            continue
        if (provider, model) in seen:
            continue
        seen.add((provider, model))
        selectable = bool(route.get("credentialConfigured"))
        if selectable_only and not selectable:
            continue
        grouped.setdefault(provider, []).append({
            "id": _custom_id(provider, model),
            "display_name": route.get("name") or model,
            "selectable": selectable,
            "provider_id": provider,
            "model_id": model,
            "source": "custom",
        })
    return [
        {"provider_id": provider, "display_name": provider, "models": models}
        for provider, models in grouped.items()
    ]


def _effective_headless_model(config_dump: str) -> tuple[Optional[str], Optional[str]]:
    """Read the official composed ``--dump-config`` output for its named plugin.

    The installed CLI exposes no structured dump switch.  This small YAML-list
    scanner follows the actual plugin boundary instead of searching arbitrary
    text with a format-dependent regex.
    """
    current_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    for raw in config_dump.splitlines():
        stripped = raw.strip()
        if stripped.startswith("- id:"):
            if current_id == "agent-default-model":
                break
            current_id = stripped.partition(":")[2].strip()
            provider = model = None
        elif current_id == "agent-default-model" and stripped.startswith("provider:"):
            provider = stripped.partition(":")[2].strip(" '\"") or None
        elif current_id == "agent-default-model" and stripped.startswith("model:"):
            model = stripped.partition(":")[2].strip(" '\"") or None
    return provider, model


def _default_launch() -> list[str]:
    env_bin = os.environ.get("DSH_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.exists():
            return ["node", str(p)]
        raise RuntimeError(f"环境变量 DSH_BIN 指向不存在的文件: {env_bin}")
    dsh = shutil.which("dsh")
    if dsh:
        return [dsh]
    if _LOCAL_DSH_BIN.exists():
        return ["node", str(_LOCAL_DSH_BIN)]
    raise RuntimeError(
        "找不到 DeepSeek Harness 启动入口（可用 launch 参数或环境变量 DSH_BIN 指定）"
    )


class DeepSeekHarnessAdapter(AgentAdapter):
    """DeepSeek Harness headless 子进程 Adapter。"""

    name = "deepseek_harness"

    @classmethod
    def discover(cls) -> dict:
        """发现本机 Harness profiles、已配置模型与 web 状态，不执行模型。"""
        errors: list[str] = []
        try:
            launch = _default_launch()
        except Exception as exc:  # noqa: BLE001
            return {
                "agent_id": cls.name,
                "display_name": "DeepSeek Harness",
                "installed": False,
                "available": False,
                "version": None,
                "errors": [str(exc)],
                "interactive": {
                    "available": False, "bridge_ready": False,
                    "command_name": "/gowrite", "command_ready": False,
                },
                "direct": {
                    "available": False, "auth_status": "not_detected",
                    "model_selection": "none", "models": [], "custom_models": [],
                    "provider_models": [], "managed_model": None, "capabilities": {},
                },
            }

        version: Optional[str] = None
        try:
            probe = subprocess.run(
                launch + ["--version"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=12,
            )
            version = next((line.strip() for line in probe.stdout.splitlines() if line.strip()), None)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Harness 版本检测失败：{exc}")

        dsh_home = Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
        credentials_path = dsh_home / ".credentials.yaml"
        auth_status = "configured" if credentials_path.is_file() and credentials_path.stat().st_size > 0 else "not_detected"

        def dump_profile(profile: str) -> Optional[str]:
            try:
                result = subprocess.run(
                    launch + ["--profile", profile, "--dump-config"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=20,
                )
                if result.returncode != 0:
                    errors.append(result.stderr.strip() or f"Harness {profile} profile 读取失败")
                    return None
                return result.stdout
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Harness {profile} profile 读取失败：{exc}")
                return None

        headless_dump = dump_profile("headless")
        provider, model = _effective_headless_model(headless_dump) if headless_dump else (None, None)
        if headless_dump and not model:
            errors.append("Harness Headless 组合配置未公开有效模型")

        try:
            snapshot = _harness_config_snapshot(launch, dsh_home)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Harness 自定义模型设置读取失败：{exc}")
            snapshot = {"routes": [], "default": {}, "providers": []}
        provider_models = _provider_models(snapshot)
        # 扁平自定义路由（向后兼容旧 UI/保存校验；按 provider 分组的权威视图
        # 见 provider_models —— 绝不硬编码 DeepSeek / Flash / Pro / token-plan）。
        custom_models = [
            {key: entry[key] for key in (
                "id", "display_name", "selectable", "provider_id", "model_id", "source",
            )}
            for provider_group in provider_models
            for entry in provider_group["models"]
        ]
        # 友好显示名来自 Harness 自身配置（pi-ai providers 的 name 字段），
        # 不硬编码 Flash/Pro 名称；找不到时如实显示模型 id。
        name_by_model: dict[str, str] = {
            str(route["model"]): str(route.get("name") or route["model"])
            for route in snapshot.get("routes", [])
        }
        native_display = name_by_model.get(model) or model
        # The base headless stack owns this route; it remains separate from
        # user-configured pi-ai profiles even when names happen to coincide.
        native_models = ([{"id": model, "display_name": native_display, "selectable": True,
                           "provider_id": provider, "model_id": model, "source": "native"}]
                         if provider and model else [])
        headless_available = bool(headless_dump and (native_models or any(item["selectable"] for item in custom_models)))

        web_dump = dump_profile("web")
        command_ready = bool(web_dump and any("gowrite" in line.lower() for line in web_dump.splitlines()))
        web_url = os.environ.get("DSH_WEB_URL", "http://127.0.0.1:3080")
        parsed_url = urllib.parse.urlsplit(web_url)
        safe_host = parsed_url.hostname or "local"
        if parsed_url.port:
            safe_host = f"{safe_host}:{parsed_url.port}"
        safe_web_url = urllib.parse.urlunsplit((parsed_url.scheme or "http", safe_host, parsed_url.path, "", ""))
        web_running = False
        try:
            with urllib.request.urlopen(web_url, timeout=2) as response:  # noqa: S310 — localhost/default 可覆盖
                web_running = 200 <= response.status < 400
        except Exception:
            web_running = False
        web_profile_available = bool(web_dump)

        return {
            "agent_id": cls.name,
            "display_name": "DeepSeek Harness",
            "installed": True,
            "available": True,
            "version": version,
            "errors": errors,
            "interactive": {
                "available": web_profile_available,
                "bridge_ready": command_ready and web_running,
                "command_name": "/gowrite",
                "command_ready": command_ready,
                "relevant_status": {
                    "profile": "web",
                    "runtime": "running" if web_running else "stopped",
                    "url": safe_web_url,
                },
                "repair_hint": None if command_ready else "Harness 已提供命令运行时，但当前 profile 未配置 Go Write 的 /gowrite 插件。",
            },
            "direct": {
                "available": headless_available,
                "auth_status": auth_status,
                # 真话语义：只有受管默认模型（无自定义路由）时如实报 managed；
                # 存在可选自定义路由时报 selectable（可选手 = 受管默认 + 自定义）。
                "model_selection": _model_selection_kind(native_models, custom_models),
                "models": native_models,
                "custom_models": custom_models,
                # 按 provider 分组的可选手目录（通用解析；DeepSeek / token-plan 等
                # 全部来自配置本身，不硬编码任何 provider/model 名）。
                "provider_models": provider_models,
                "managed_model": ({"id": model, "display_name": native_display, "provider_id": provider} if model else None),
                "capabilities": cls(launch=launch).capabilities(),
                "executable_path": " ".join(launch),
            },
        }

    def __init__(
        self,
        launch: Optional[list[str]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """launch：可执行起点 argv（如 ["node", ".../bin.js"] 或 ["dsh"]）。"""
        self._launch = launch if launch is not None else _default_launch()
        self._dsh_home = Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))
        self._timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._cancelled = threading.Event()

    # ---------------- 能力声明（只按当前真实能力） ----------------

    def capabilities(self) -> dict:
        return {
            "run": True,
            "cwd": True,
            "final_output": True,
            "cancel": True,
            "stream": False,          # headless 仅最终消息，无流式
            "resume": False,          # headless 不支持恢复会话
            "session": False,         # headless 不输出 session_id
            "model_selection": "profile_managed",  # 模型由 Harness profile 配置决定
        }

    # ---------------- 执行 ----------------

    def _selection_overlay(self, request: AgentRequest, temporary: Path) -> list[str]:
        """Create a one-process settings override; never edit Harness home."""
        if bool(request.model) == bool(request.custom_model):
            raise RuntimeError("请选择一个 Harness 内置模型或自定义模型")
        base_provider, base_model = _effective_headless_model(
            subprocess.run(self._launch + ["--profile", "headless", "--dump-config"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=20).stdout
        )
        if request.custom_model:
            provider, model = _selection_from_custom(
                request.custom_model, _harness_config_snapshot(self._launch, self._dsh_home).get("routes", []),
            )
        else:
            if not base_provider or request.model != base_model:
                raise RuntimeError("所选 Harness 内置模型当前不可用")
            provider, model = base_provider, base_model
        source = self._dsh_home / "settings.yaml"
        if not source.is_file():
            raise RuntimeError("Harness 设置文件未检测到")
        settings_copy = temporary / "settings.yaml"
        patch_file = temporary / "selection.patch.yml"
        code = """
import fs from 'node:fs'; import YAML from 'yaml';
const document = YAML.parse(fs.readFileSync(process.argv[1], 'utf8')) || {};
document['agent-default-model'] = { provider: process.argv[3], model: process.argv[4] };
fs.writeFileSync(process.argv[2], YAML.stringify(document), { mode: 0o600 });
"""
        root = _harness_package_root(self._launch)
        result = subprocess.run([self._launch[0], "--input-type=module", "-e", code, str(source), str(settings_copy), provider, model], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12, cwd=root)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Harness 临时选择配置创建失败")
        patch_file.write_text(f"- id: settings\n  config:\n    path: {settings_copy.as_posix()}\n", encoding="utf-8")
        return ["--patch", str(patch_file)]

    def run(self, request: AgentRequest) -> AgentResult:
        self._cancelled.clear()
        temporary_context = None
        if request.model or request.custom_model:
            try:
                temporary_context = tempfile.TemporaryDirectory(prefix="ai-write-harness-")
                overlay = self._selection_overlay(request, Path(temporary_context.name))
            except Exception as exc:  # noqa: BLE001
                return AgentResult(status="failed", error=str(exc), agent=self.name)
            cmd = self._launch + ["--profile", "headless"] + overlay + [request.task]
        else:
            # The settings operation never reaches this path.  Keep it for
            # adapter-level callers that intentionally exercise raw launch.
            cmd = self._launch + ["--profile", "headless", request.task]
        with self._lock:
            if self._proc is not None:
                return AgentResult(status="failed", error="adapter 已有任务在运行", agent=self.name)
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=request.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception as exc:  # noqa: BLE001
                return AgentResult(status="failed", error=f"启动失败: {exc}", agent=self.name)
            self._proc = proc

        try:
            out, err = proc.communicate(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            with self._lock:
                self._proc = None
            try:
                proc.kill()
                proc.communicate()
            except Exception:  # noqa: BLE001
                pass
            return AgentResult(status="failed", error=f"超时（{self._timeout} 秒）", agent=self.name)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._proc = None
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            return AgentResult(status="failed", error=str(exc), agent=self.name)
        finally:
            with self._lock:
                self._proc = None
            if temporary_context is not None:
                temporary_context.cleanup()

        if self._cancelled.is_set():
            return AgentResult(
                status="cancelled", output=out.strip(), agent=self.name,
                exit_code=proc.returncode,
            )
        if proc.returncode != 0:
            return AgentResult(
                status="failed", output=out.strip(),
                error=(err.strip() or f"非 0 退出码 {proc.returncode}"),
                agent=self.name, exit_code=proc.returncode,
            )
        return AgentResult(status="completed", output=out.strip(), agent=self.name,
                           exit_code=proc.returncode)

    def cancel(self) -> bool:
        """终止当前运行中的子进程；成功终止返回 True，结果转 cancelled。"""
        with self._lock:
            proc = self._proc
        if proc is None or proc.poll() is not None:
            return False
        self._cancelled.set()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False
        return True
