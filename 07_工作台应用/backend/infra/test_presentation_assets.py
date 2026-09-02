# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infra import presentation_assets as assets  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"fixture"


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "config"))
    project_dir = tmp_path / "project"
    (project_dir / "_工作台状态").mkdir(parents=True)
    project_id = "project-1"
    monkeypatch.setattr(assets, "get_project_snapshot", lambda value: {
        "identity": {"project_dir": str(project_dir)},
        "current": {"characters": [{"source_ref": "char-1"}]}, "future": {"characters": []},
    } if value == project_id else (_ for _ in ()).throw(assets.ProjectSnapshotError("作品不存在")))
    image = tmp_path / "source.png"
    image.write_bytes(PNG)
    return project_id, project_dir, image


def test_global_replace_reset_and_no_source_path(project):
    _project_id, _project_dir, image = project
    assert assets.get_global_presentation()["illustrations"]["city"]["has_custom"] is False
    result = assets.set_global_illustration("city", str(image))
    assert result["illustrations"]["city"]["image_src"].startswith("data:image/png;base64,")
    metadata = json.loads((Path(__import__("os").environ["AI_WRITE_CONFIG_DIR"]) / "presentation.json").read_text(encoding="utf-8"))
    assert str(image) not in json.dumps(metadata) and "iVBOR" not in json.dumps(metadata)
    assets.reset_global_illustration("city")
    assert assets.get_global_presentation()["illustrations"]["city"]["image_src"] is None


def test_project_cover_and_avatar_are_isolated_and_reloadable(project):
    project_id, project_dir, image = project
    assets.set_project_cover(project_id, str(image))
    assets.set_character_avatar(project_id, "char-1", str(image))
    read_again = assets.get_project_presentation(project_id)
    assert read_again["project_cover"]["has_custom"] is True
    assert read_again["character_avatars"]["char-1"]["has_custom"] is True
    metadata = json.loads((project_dir / "_工作台状态" / "presentation.json").read_text(encoding="utf-8"))
    assert str(image) not in json.dumps(metadata) and "data:image" not in json.dumps(metadata)
    assets.reset_character_avatar(project_id, "char-1")
    assert assets.get_project_presentation(project_id)["character_avatars"] == {}


def test_bad_input_and_invalid_character_preserve_existing_binding(project, tmp_path):
    project_id, _project_dir, image = project
    assets.set_project_cover(project_id, str(image))
    bad = tmp_path / "bad.jpg"
    bad.write_text("not an image", encoding="utf-8")
    with pytest.raises(assets.PresentationAssetError):
        assets.set_project_cover(project_id, str(bad))
    assert assets.get_project_presentation(project_id)["project_cover"]["has_custom"] is True
    with pytest.raises(assets.PresentationAssetError):
        assets.set_character_avatar(project_id, "not-a-character", str(image))
