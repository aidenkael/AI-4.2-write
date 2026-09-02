# -*- coding: utf-8 -*-
"""Persistent, non-semantic presentation assets for the Go Write desktop app.

This module owns only managed image files and their small local metadata.  It
never mutates ProjectModel, Story State, Author Intent, or the change ledger.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from operations.project_snapshot import ProjectSnapshotError, get_project_snapshot

_ALLOWED = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_MAX_BYTES = 8 * 1024 * 1024
_GLOBAL_SLOTS = {"city", "mountains", "desk"}


class PresentationAssetError(Exception):
    """A local presentation asset could not be safely used."""


def _config_dir() -> Path:
    return Path(os.environ.get("AI_WRITE_CONFIG_DIR") or Path.home() / ".ai-write").resolve()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresentationAssetError("展示图片配置损坏，未改动现有图片。") from exc
    if not isinstance(value, dict):
        raise PresentationAssetError("展示图片配置格式无效，未改动现有图片。")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".presentation-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _image_type(path: Path) -> tuple[str, str]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PresentationAssetError("所选图片不存在或无法读取。") from exc
    if not resolved.is_file():
        raise PresentationAssetError("所选路径不是普通图片文件。")
    suffix = resolved.suffix.lower()
    mime = _ALLOWED.get(suffix)
    if not mime:
        raise PresentationAssetError("只支持 PNG、JPG、JPEG 或 WEBP 图片。")
    try:
        size = resolved.stat().st_size
        header = resolved.read_bytes()[:16]
    except OSError as exc:
        raise PresentationAssetError("无法读取所选图片。") from exc
    if size <= 0 or size > _MAX_BYTES:
        raise PresentationAssetError("图片必须大于 0 且不超过 8MB。")
    signatures = {
        "image/png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": header.startswith(b"\xff\xd8\xff"),
        "image/webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    }
    if not signatures[mime]:
        raise PresentationAssetError("图片内容与文件类型不匹配。")
    return suffix, mime


def _image_src(path: Path) -> str | None:
    if not path.is_file():
        return None
    suffix, mime = _image_type(path)
    del suffix
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _safe_managed_file(root: Path, name: object) -> Path | None:
    if not isinstance(name, str) or not name:
        return None
    candidate = (root / name).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _replace(metadata_path: Path, asset_root: Path, metadata: dict[str, Any], key: str, source: str) -> dict[str, Any]:
    source_path = Path(source)
    suffix, _ = _image_type(source_path)
    asset_root.mkdir(parents=True, exist_ok=True)
    old = _safe_managed_file(asset_root, metadata.get(key))
    new_name = f"{uuid.uuid4().hex}{suffix}"
    destination = asset_root / new_name
    temp = asset_root / f".copy-{uuid.uuid4().hex}{suffix}"
    try:
        shutil.copyfile(source_path, temp)
        os.replace(temp, destination)
        next_metadata = dict(metadata)
        next_metadata[key] = new_name
        _write_json_atomic(metadata_path, next_metadata)
    except Exception:
        temp.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    if old and old != destination:
        old.unlink(missing_ok=True)
    return next_metadata


def _copy_managed(asset_root: Path, source: str) -> tuple[Path, str]:
    source_path = Path(source)
    suffix, _ = _image_type(source_path)
    asset_root.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    destination = asset_root / name
    temp = asset_root / f".copy-{uuid.uuid4().hex}{suffix}"
    try:
        shutil.copyfile(source_path, temp)
        os.replace(temp, destination)
    except Exception:
        temp.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    return destination, name


def _reset(metadata_path: Path, asset_root: Path, metadata: dict[str, Any], key: str) -> dict[str, Any]:
    old = _safe_managed_file(asset_root, metadata.get(key))
    if key not in metadata:
        return metadata
    next_metadata = dict(metadata)
    del next_metadata[key]
    _write_json_atomic(metadata_path, next_metadata)
    if old:
        old.unlink(missing_ok=True)
    return next_metadata


def _project_paths(project_id: str) -> tuple[Path, Path, dict[str, Any]]:
    try:
        snapshot = get_project_snapshot(project_id)
    except ProjectSnapshotError as exc:
        raise PresentationAssetError(str(exc)) from exc
    project_dir = Path(snapshot["identity"]["project_dir"]).resolve()
    state_dir = project_dir / "_工作台状态"
    return state_dir / "presentation.json", state_dir / "presentation_assets", snapshot


def _project_metadata(project_id: str) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    metadata_path, asset_root, snapshot = _project_paths(project_id)
    metadata = _read_json(metadata_path)
    if any(key not in {"project_cover", "character_avatars"} for key in metadata):
        raise PresentationAssetError("展示图片配置包含不支持的字段，未改动现有图片。")
    avatars = metadata.get("character_avatars", {})
    if not isinstance(avatars, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in avatars.items()):
        raise PresentationAssetError("人物头像配置格式无效，未改动现有图片。")
    return metadata_path, asset_root, snapshot, metadata


def _character_refs(snapshot: dict[str, Any]) -> set[str]:
    return {
        str(item.get("source_ref"))
        for bucket in ("current", "future")
        for item in snapshot.get(bucket, {}).get("characters", [])
        if isinstance(item, dict) and isinstance(item.get("source_ref"), str) and item.get("source_ref")
    }


def get_global_presentation() -> dict[str, Any]:
    root = _config_dir() / "presentation_assets"
    metadata = _read_json(_config_dir() / "presentation.json")
    slots = metadata.get("illustrations", {})
    if not isinstance(slots, dict):
        raise PresentationAssetError("界面图片配置格式无效。")
    return {"illustrations": {slot: {"slot": slot, "has_custom": bool(_safe_managed_file(root, slots.get(slot))), "image_src": _image_src(path) if (path := _safe_managed_file(root, slots.get(slot))) else None} for slot in sorted(_GLOBAL_SLOTS)}}


def set_global_illustration(slot: str, local_path: str) -> dict[str, Any]:
    if slot not in _GLOBAL_SLOTS:
        raise PresentationAssetError("未知的界面图片位置。")
    config = _config_dir()
    metadata_path, root = config / "presentation.json", config / "presentation_assets"
    metadata = _read_json(metadata_path)
    slots = metadata.get("illustrations", {})
    if not isinstance(slots, dict):
        raise PresentationAssetError("界面图片配置格式无效，未改动现有图片。")
    holder = {str(key): value for key, value in slots.items() if isinstance(value, str)}
    old = _safe_managed_file(root, holder.get(slot))
    destination, name = _copy_managed(root, local_path)
    try:
        _write_json_atomic(metadata_path, {**metadata, "illustrations": {**holder, slot: name}})
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if old:
        old.unlink(missing_ok=True)
    return get_global_presentation()


def reset_global_illustration(slot: str) -> dict[str, Any]:
    if slot not in _GLOBAL_SLOTS:
        raise PresentationAssetError("未知的界面图片位置。")
    config = _config_dir()
    metadata_path, root = config / "presentation.json", config / "presentation_assets"
    metadata = _read_json(metadata_path)
    slots = metadata.get("illustrations", {})
    if not isinstance(slots, dict):
        raise PresentationAssetError("界面图片配置格式无效。")
    name = slots.get(slot)
    old = _safe_managed_file(root, name)
    next_slots = {str(k): v for k, v in slots.items() if isinstance(v, str) and k != slot}
    _write_json_atomic(metadata_path, {**metadata, "illustrations": next_slots})
    if old:
        old.unlink(missing_ok=True)
    return get_global_presentation()


def get_project_presentation(project_id: str) -> dict[str, Any]:
    metadata_path, root, _snapshot, metadata = _project_metadata(project_id)
    del metadata_path
    cover = _safe_managed_file(root, metadata.get("project_cover"))
    avatars = metadata.get("character_avatars", {})
    return {
        "project_id": project_id,
        "project_cover": {"has_custom": bool(cover), "image_src": _image_src(cover) if cover else None},
        "character_avatars": {
            ref: {"source_ref": ref, "has_custom": bool(path), "image_src": _image_src(path) if path else None}
            for ref, name in avatars.items() if (path := _safe_managed_file(root, name))
        },
    }


def set_project_cover(project_id: str, local_path: str) -> dict[str, Any]:
    metadata_path, root, _snapshot, metadata = _project_metadata(project_id)
    _replace(metadata_path, root, metadata, "project_cover", local_path)
    return get_project_presentation(project_id)


def reset_project_cover(project_id: str) -> dict[str, Any]:
    metadata_path, root, _snapshot, metadata = _project_metadata(project_id)
    _reset(metadata_path, root, metadata, "project_cover")
    return get_project_presentation(project_id)


def set_character_avatar(project_id: str, source_ref: str, local_path: str) -> dict[str, Any]:
    metadata_path, root, snapshot, metadata = _project_metadata(project_id)
    if source_ref not in _character_refs(snapshot):
        raise PresentationAssetError("人物头像只能绑定当前作品中活动的人物记录。")
    avatars = dict(metadata.get("character_avatars", {}))
    old = _safe_managed_file(root, avatars.get(source_ref))
    destination, name = _copy_managed(root, local_path)
    avatars[source_ref] = name
    final: dict[str, Any] = {"character_avatars": avatars}
    if isinstance(metadata.get("project_cover"), str):
        final["project_cover"] = metadata["project_cover"]
    try:
        _write_json_atomic(metadata_path, final)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if old:
        old.unlink(missing_ok=True)
    return get_project_presentation(project_id)


def reset_character_avatar(project_id: str, source_ref: str) -> dict[str, Any]:
    metadata_path, root, snapshot, metadata = _project_metadata(project_id)
    if source_ref not in _character_refs(snapshot):
        raise PresentationAssetError("人物头像只能绑定当前作品中活动的人物记录。")
    avatars = dict(metadata.get("character_avatars", {}))
    old = _safe_managed_file(root, avatars.get(source_ref))
    avatars.pop(source_ref, None)
    payload: dict[str, Any] = {"character_avatars": avatars}
    if isinstance(metadata.get("project_cover"), str):
        payload["project_cover"] = metadata["project_cover"]
    _write_json_atomic(metadata_path, payload)
    if old:
        old.unlink(missing_ok=True)
    return get_project_presentation(project_id)
