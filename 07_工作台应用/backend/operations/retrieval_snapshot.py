# -*- coding: utf-8 -*-
"""请求级检索快照 CLI：/gowrite 或 Direct 执行内"唯一一次确定性检索调用"的薄入口。

Agent 在执行内运行（全部任务模板显式内嵌 --request <request_id>）：

    StoryPlan：  python retrieval_snapshot.py --request <request_id> "<query>"
    StoryWrite： python retrieval_snapshot.py --request <request_id> "<query>"

显式绑定 request_id（P0 精确绑定）：Direct 请求绝不进入 active.json，
检索命令绝不依赖可变的 active 指针（2026-08-27 起 StoryPlan 也改为显式绑定）。

该调用做两件事（同一 invocation）：
1. 运行现有 KnowledgeRetrieve（确定性、无模型调用、只读），得到精确
   RetrievalPackage；
2. 把该包的精确序列化（含 request_id / project_id / turn_id / 归一化
   query / package_fingerprint）写入当前请求的临时快照（StoryPlan → planning
   dir；StoryWrite → writing dir；非权威、可删除、随临时生命周期清理）。

随后向 stdout 打印 `{package_fingerprint, package}` JSON：模型只从该显示包中
选择 selection_ref（source_kind/source_id/source_anchor；统一多源混合包）并原样回显
package_fingerprint。

Go Write finalize **绝不再次执行 KnowledgeRetrieve**：只读取该快照、校验身份、
反序列化并把同一包绑定给 Context。快照缺失/身份或查询不匹配 → 整轮 failed。

本文件是纯胶水：不重新实现检索，不复制 StoryPlan/StoryWrite 业务规则。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from operations import qoder_bridge as bridge  # noqa: E402
from operations import story_planning  # noqa: E402
from operations import story_writing  # noqa: E402
from operations import review  # noqa: E402
from operations import new_project  # noqa: E402


def _usage() -> int:
    print(
        "用法：python retrieval_snapshot.py \"<query>\"\n"
        "  或：python retrieval_snapshot.py --request <request_id> \"<query>\"",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    args = sys.argv[1:]
    request_id = None
    if args and args[0] == "--request":
        if len(args) < 2:
            return _usage()
        request_id = args[1]
        args = args[2:]
    if not args or not (args[0] or "").strip():
        return _usage()
    query = args[0].strip()

    if request_id is None:
        # 全部任务模板（StoryPlan/StoryWrite/Review/NewProject）都显式内嵌
        # --request <request_id>（Direct 请求绝不进入 active.json，检索命令
        # 绝不依赖可变 active 指针）。
        raise story_planning.StoryPlanningError(
            "缺少 --request <request_id>：检索命令必须显式绑定请求 id。"
        )

    request = bridge.get_request(request_id)
    if request is None:
        raise story_planning.StoryPlanningError(
            "任务文件不存在或不可读，无法生成检索快照。"
        )
    kind = request.get("kind") or ""

    if kind == "story_write_propose":
        package = story_writing.execute_request_scoped_retrieval(query, request_id)
    elif kind == "review_propose":
        package = review.execute_request_scoped_retrieval(query, request_id)
    elif kind == "story_design_propose":
        package = new_project.execute_request_scoped_retrieval(query, request_id)
    else:
        # StoryPlan：显式 --request 绑定（与其余操作同一 P0 精确绑定）
        package = story_planning.execute_request_scoped_retrieval(query, request_id)

    print(json.dumps(
        {
            "package_fingerprint": story_planning._package_fingerprint(package),
            "package": story_planning._package_snapshot_dict(package),
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
