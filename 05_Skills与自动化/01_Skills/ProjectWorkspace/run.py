# -*- coding: utf-8 -*-
"""ProjectWorkspace CLI — 机械操作入口。

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

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from project_workspace import (
    list_projects,
    resolve_project,
    create_project,
    accept_prose,
    get_recent_prose,
    WorkspaceError,
)


def cmd_list(args):
    """列出所有项目。"""
    projects = list_projects()
    if not projects:
        print("没有项目")
        return
    
    for proj in projects:
        print(f"{proj['name']} (id={proj['project_id']})")


def cmd_resolve(args):
    """解析项目。"""
    try:
        proj = resolve_project(args.project)
        print(f"名称: {proj['name']}")
        print(f"ID: {proj['project_id']}")
        print(f"目录: {proj['project_dir']}")
    except WorkspaceError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_create(args):
    """创建项目。"""
    author_intent = None
    if args.intent_json:
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
    """获取最近接受的正文。"""
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
    """接受正文。"""
    if not args.author_accepted:
        print("错误: 必须设置 --author-accepted", file=sys.stderr)
        sys.exit(1)
    
    # 读取 prose 文件
    prose_path = Path(args.prose_file)
    if not prose_path.exists():
        print(f"文件不存在: {prose_path}", file=sys.stderr)
        sys.exit(1)
    
    accepted_text = prose_path.read_text(encoding="utf-8")
    
    # 读取 settlement（如果提供）
    settlement = None
    if args.settlement_json:
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
        print(f"已接受正文")
        print(f"章节: {result['chapter_path']}")
        print(f"Scene ref: {result['scene_ref']}")
        print(f"State rev: {result['state_rev']}")
    except WorkspaceError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="ProjectWorkspace CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # list
    subparsers.add_parser("list", help="列出所有项目")
    
    # resolve
    resolve_parser = subparsers.add_parser("resolve", help="解析项目")
    resolve_parser.add_argument("--project", type=str, default=None, help="作品名或 project_id")
    
    # create
    create_parser = subparsers.add_parser("create", help="创建项目")
    create_parser.add_argument("--name", type=str, required=True, help="作品名")
    create_parser.add_argument("--intent-json", type=str, default=None, help="作者意图 JSON 文件路径")
    
    # recent
    recent_parser = subparsers.add_parser("recent", help="获取最近接受的正文")
    recent_parser.add_argument("--project", type=str, default=None, help="作品名或 project_id")
    
    # accept
    accept_parser = subparsers.add_parser("accept", help="接受正文")
    accept_parser.add_argument("--project", type=str, default=None, help="作品名或 project_id")
    accept_parser.add_argument("--chapter", type=int, required=True, help="章节号")
    accept_parser.add_argument("--scene-ref", type=str, required=True, help="场景引用")
    accept_parser.add_argument("--prose-file", type=str, required=True, help="正文文件路径")
    accept_parser.add_argument("--settlement-json", type=str, default=None, help="Settlement JSON 文件路径")
    accept_parser.add_argument("--author-accepted", action="store_true", help="作者接受标志")
    
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

