# -*- coding: utf-8 -*-
"""ProjectWorkspace CLI — 机械操作入口（F0.1）。

不做：
- 自然语言解析
- LLM 调用
- Prompt Router
- Git commit/push
- BKP 自动选择
- 文学判断
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from project_workspace import (
    list_projects,
    resolve_project,
    create_project,
    accept_prose,
    get_recent_prose,
    persist_state_transition,
    load_project,
    WorkspaceError,
)


def cmd_list(args):
    projects = list_projects()
    if not projects:
        print("没有项目")
        return
    for proj in projects:
        print(f"{proj['name']} (id={proj['project_id']})")


def cmd_resolve(args):
    try:
        proj = resolve_project(args.project)
        print(f"名称: {proj['name']}")
        print(f"ID: {proj['project_id']}")
        print(f"目录: {proj['project_dir']}")
    except WorkspaceError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_create(args):
    intent_path = Path(args.intent_json)
    if not intent_path.exists():
        print(f"文件不存在: {intent_path}", file=sys.stderr)
        sys.exit(1)
    author_intent = json.loads(intent_path.read_text(encoding="utf-8"))
    try:
        proj = create_project(args.name, author_intent)
        print(f"已创建项目: {proj['name']}")
        print(f"ID: {proj['project_id']}")
        print(f"目录: {proj['project_dir']}")
    except WorkspaceError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_recent(args):
    try:
        proj = resolve_project(args.project)
        prose = get_recent_prose(proj["project_dir"])
        if prose is None:
            print("没有接受的正文")
        else:
            print(prose)
    except WorkspaceError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_accept(args):
    if not args.author_accepted:
        print("错误: 必须设置 --author-accepted", file=sys.stderr)
        sys.exit(1)

    prose_path = Path(args.prose_file)
    if not prose_path.exists():
        print(f"文件不存在: {prose_path}", file=sys.stderr)
        sys.exit(1)
    accepted_text = prose_path.read_text(encoding="utf-8")

    # Settlement is REQUIRED at CLI level too.
    if not args.settlement_json:
        print("错误: 必须提供 --settlement-json", file=sys.stderr)
        sys.exit(1)
    settlement_path = Path(args.settlement_json)
    if not settlement_path.exists():
        print(f"文件不存在: {settlement_path}", file=sys.stderr)
        sys.exit(1)
    settlement = json.loads(settlement_path.read_text(encoding="utf-8"))

    try:
        proj = resolve_project(args.project)
        result = accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=args.chapter,
            scene_ref=args.scene_ref,
            accepted_text=accepted_text,
            settlement=settlement,
            author_accepted=True,
        )
        print("已接受正文")
        print(f"章节: {result['chapter_path']}")
        print(f"Scene ref: {result['scene_ref']}")
        print(f"State rev: {result['state_rev']}")
    except WorkspaceError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="ProjectWorkspace CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="列出所有项目")

    resolve_parser = subparsers.add_parser("resolve", help="解析项目")
    resolve_parser.add_argument("--project", type=str, default=None)

    create_parser = subparsers.add_parser("create", help="创建项目")
    create_parser.add_argument("--name", type=str, required=True)
    create_parser.add_argument("--intent-json", type=str, required=True,
                               help="完整 author_intent JSON 文件路径（必需）")

    recent_parser = subparsers.add_parser("recent", help="获取最近接受的正文")
    recent_parser.add_argument("--project", type=str, default=None)

    accept_parser = subparsers.add_parser("accept", help="接受正文")
    accept_parser.add_argument("--project", type=str, default=None)
    accept_parser.add_argument("--chapter", type=int, required=True)
    accept_parser.add_argument("--scene-ref", type=str, required=True)
    accept_parser.add_argument("--prose-file", type=str, required=True)
    accept_parser.add_argument("--settlement-json", type=str, required=True,
                               help="Settlement JSON 文件路径（必需）")
    accept_parser.add_argument("--author-accepted", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "resolve":
        cmd_resolve(args)
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "recent":
        cmd_recent(args)
    elif args.command == "accept":
        cmd_accept(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
