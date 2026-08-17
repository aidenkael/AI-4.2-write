# -*- coding: utf-8 -*-
"""Views：正式状态 → UI 展示数据。

只做形状转换与字段裁剪；不拥有第二套故事事实，不做任何计算性“进度/字数/百分比”字段。
"""
from __future__ import annotations


def list_view(projects: list[dict]) -> list[dict]:
    """列表项：只暴露 UI 需要的稳定字段（project_id + name）。"""
    return [
        {"project_id": p.get("project_id"), "name": p.get("name")}
        for p in projects
    ]


def open_view(project: dict) -> dict:
    """打开结果：只暴露 {project_id, name}（project_dir 留在服务端，不进 UI）。"""
    return {"project_id": project["project_id"], "name": project["name"]}


def overview_view(overview: dict) -> dict:
    """概览展示形状：操作层已是最小可序列化结构，直接透传。"""
    return overview
