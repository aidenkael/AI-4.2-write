"""Knowledge catalog discovery：自动发现全部可检索知识来源（通用多源）。

三类来源（确定性发现，无模型、无向量库）：
- reference provider:  02_素材知识库/*/bkp/identity.json（参考作品 BKP；保持现有布局）
- method provider:     02_素材知识库/*/method/identity.json
                       仅 schema_version=gowrite_method_knowledge/v1 且
                       schema_status=FINALIZED_RETRIEVAL_READY 的方法知识包可检索
- validated provider:  04_写作知识库/**/identity.json
                       仅 schema_version=gowrite_validated_knowledge/v1 且
                       schema_status=FINALIZED_VALIDATED 的已验证知识包可检索
"""

import json
from pathlib import Path

METHOD_SCHEMA_VERSION = "gowrite_method_knowledge/v1"
VALIDATED_SCHEMA_VERSION = "gowrite_validated_knowledge/v1"


def _read_identity(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _reference_source(bkp_dir: Path, identity: dict) -> dict | None:
    try:
        return {
            "source_kind": "reference_bkp",
            "source_id": identity["book"]["book_id"],
            "title": identity["book"]["title"],
            "author": identity["book"]["author"],
            "category": identity["book"].get("category", ""),
            "package_dir": str(bkp_dir),
            "identity": identity,
        }
    except KeyError:
        return None


def _method_source(method_dir: Path, identity: dict) -> dict | None:
    if identity.get("schema_version") != METHOD_SCHEMA_VERSION:
        return None
    if identity.get("schema_status") != "FINALIZED_RETRIEVAL_READY":
        return None  # 未定稿的方法包不可检索（确定性门控）
    if not identity.get("source_id"):
        return None
    return {
        "source_kind": "method_source",
        "source_id": str(identity["source_id"]),
        "title": identity.get("title") or "",
        "author": identity.get("author") or "",
        "category": "",
        "package_dir": str(method_dir),
        "identity": identity,
    }


def _validated_source(pkg_dir: Path, identity: dict) -> dict | None:
    if identity.get("schema_version") != VALIDATED_SCHEMA_VERSION:
        return None
    if identity.get("schema_status") != "FINALIZED_VALIDATED":
        return None  # 只有显式定稿验证包可检索；缺包 = 合法状态
    if not identity.get("source_id"):
        return None
    return {
        "source_kind": "validated_knowledge",
        "source_id": str(identity["source_id"]),
        "title": identity.get("title") or "",
        "author": "",
        "category": "",
        "package_dir": str(pkg_dir),
        "identity": identity,
    }


def discover_sources(base_dir: str) -> list[dict]:
    """扫描全部知识存储，返回统一来源描述列表（不区分子目录顺序以外的优先级）。"""
    base = Path(base_dir)
    sources: list[dict] = []

    distill_dir = base / "02_素材知识库"
    if distill_dir.exists():
        for asset_dir in sorted(distill_dir.iterdir()):
            if not asset_dir.is_dir():
                continue
            bkp_identity_path = asset_dir / "bkp" / "identity.json"
            if bkp_identity_path.exists():
                identity = _read_identity(bkp_identity_path)
                if identity is None:
                    print(f"[WARN] Failed to load {bkp_identity_path}")
                else:
                    source = _reference_source(asset_dir / "bkp", identity)
                    if source:
                        sources.append(source)
            method_identity_path = asset_dir / "method" / "identity.json"
            if method_identity_path.exists():
                identity = _read_identity(method_identity_path)
                if identity is None:
                    print(f"[WARN] Failed to load {method_identity_path}")
                else:
                    source = _method_source(asset_dir / "method", identity)
                    if source:
                        sources.append(source)

    validated_dir = base / "04_写作知识库"
    if validated_dir.exists():
        for identity_path in sorted(validated_dir.rglob("identity.json")):
            identity = _read_identity(identity_path)
            if identity is None:
                print(f"[WARN] Failed to load {identity_path}")
                continue
            source = _validated_source(identity_path.parent, identity)
            if source:
                sources.append(source)

    return sources
