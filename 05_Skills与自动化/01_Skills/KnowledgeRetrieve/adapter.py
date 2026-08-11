"""BKP Adapter: parse Markdown knowledge files into structured KnowledgeItems.

Handles two observed formats:
- 一九八四: `text（chapters/NNNN.md#LNN，conf）[scope: ...][boundary: ...]`
- 三体: `text｜证据：chapters/NNNN.md#LNN｜置信度：conf`
"""

import re
from pathlib import Path
from models import KnowledgeItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _extract_refs_pipe(text: str) -> tuple:
    """Extract evidence refs from pipe-delimited format: ｜证据：refs｜置信度：conf"""
    evidence = []
    confidence = None
    rest = text

    m_ev = re.findall(r"证据[：:](.+?)(?=｜|$)", text)
    if m_ev:
        for chunk in m_ev:
            refs = [r.strip() for r in re.split(r"[；;，,]", chunk) if r.strip()]
            evidence.extend(refs)
        rest = re.sub(r"｜?证据[：:].+?(?=｜|$)", "", rest).strip()

    m_conf = re.search(r"置信度[：:]\s*(高|中|低)", text)
    if m_conf:
        confidence = m_conf.group(1)
        rest = re.sub(r"｜?置信度[：:].+?(?=｜|$)", "", rest).strip()

    rest = rest.strip("｜| ")
    return evidence, confidence, rest


def _extract_refs_paren(text: str) -> tuple:
    """Extract evidence refs from parenthesized format: （chapters/NNNN.md#LNN，conf）"""
    evidence = []
    confidence = None
    scope = None
    boundary = None
    rest = text

    # Extract [scope: ...]
    m_scope = re.search(r"\[scope:\s*(.+?)\]", text)
    if m_scope:
        scope = m_scope.group(1).strip()
        rest = re.sub(r"\[scope:\s*.+?\]", "", rest).strip()

    # Extract [boundary: ...]
    m_boundary = re.search(r"\[boundary:\s*(.+?)\]", text)
    if m_boundary:
        boundary = m_boundary.group(1).strip()
        rest = re.sub(r"\[boundary:\s*.+?\]", "", rest).strip()

    # Extract parenthesized (chapters/...#LNN-LNN，conf)
    m_paren = re.search(r"（([^）]+?)）", rest)
    if m_paren:
        inner = m_paren.group(1)
        # Try to split refs and confidence
        parts = re.split(r"[，,]", inner)
        for p in parts:
            p = p.strip()
            if re.match(r"^(chapters?|ch_)\S+", p):
                evidence.append(p)
            elif p in ("高", "中", "低"):
                confidence = p
            elif re.match(r"^[a-z_/]+\.md", p):
                evidence.append(p)
        rest = re.sub(r"（[^）]+?）", "", rest).strip()

    return evidence, confidence, scope, boundary, rest


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------

def parse_observations(bkp_dir: str, book_id: str, book_title: str) -> list:
    """Parse knowledge/observations.md into KnowledgeItems."""
    text = _read(Path(bkp_dir) / "knowledge" / "observations.md")
    if not text:
        return []

    items = []
    current_dim = ""

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Dimension header: ## 维度名（N 条） or ## 维度名?N ?? (三体 encoding artifact)
        m_dim = re.match(r"^##\s+(.+)", line)
        if m_dim:
            dim_text = m_dim.group(1).strip()
            # Remove trailing count patterns: （21 条）, ?36 ??, (12条), etc.
            dim_text = re.sub(r"[（(?\s]*\d+\s*条[）)?\s]*$", "", dim_text).strip()
            # Remove trailing ?N ?? pattern (三体 encoding artifact)
            dim_text = re.sub(r"\?+\d+\s*\?*+$", "", dim_text).strip()
            if dim_text:
                current_dim = dim_text
            continue

        if not line.startswith("- "):
            continue

        bullet = line[2:].strip()
        if not bullet:
            continue

        # Detect format: pipe-delimited (三体) or parenthesized (一九八四)
        if "｜证据：" in bullet or "|证据:" in bullet:
            evidence, confidence, clean_text = _extract_refs_pipe(bullet)
            scope = None
            boundary = None
        else:
            evidence, confidence, scope, boundary, clean_text = _extract_refs_paren(bullet)

        items.append(KnowledgeItem(
            book_id=book_id,
            book_title=book_title,
            knowledge_level="Observation",
            dimension=current_dim,
            text=clean_text if clean_text else bullet,
            source_file="knowledge/observations.md",
            source_anchor=f"dim:{current_dim}",
            evidence=evidence,
            scope=scope,
            boundary=boundary,
            confidence=confidence,
        ))

    return items


# ---------------------------------------------------------------------------
# Inferences
# ---------------------------------------------------------------------------

def parse_inferences(bkp_dir: str, book_id: str, book_title: str) -> list:
    """Parse knowledge/inferences.md into KnowledgeItems."""
    text = _read(Path(bkp_dir) / "knowledge" / "inferences.md")
    if not text:
        return []

    items = []
    current_section = ""

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Section header: ## 第X部（N 条） or ## ch_NNNN
        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        if not line.startswith("- "):
            continue

        bullet = line[2:].strip()
        # Remove [INFERENCE] prefix
        bullet = re.sub(r"^\*?\[INFERENCE\]\*?\s*", "", bullet).strip()
        if not bullet:
            continue

        if "｜证据：" in bullet or "|证据:" in bullet:
            evidence, confidence, clean_text = _extract_refs_pipe(bullet)
            scope = None
            boundary = None
        else:
            evidence, confidence, scope, boundary, clean_text = _extract_refs_paren(bullet)

        items.append(KnowledgeItem(
            book_id=book_id,
            book_title=book_title,
            knowledge_level="Inference",
            dimension=current_section,
            text=clean_text if clean_text else bullet,
            source_file="knowledge/inferences.md",
            source_anchor=f"section:{current_section}",
            evidence=evidence,
            scope=scope,
            boundary=boundary,
            confidence=confidence,
        ))

    return items


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

def parse_patterns(bkp_dir: str, book_id: str, book_title: str) -> list:
    """Parse knowledge/patterns.md into KnowledgeItems."""
    text = _read(Path(bkp_dir) / "knowledge" / "patterns.md")
    if not text:
        return []

    items = []
    current_section = ""

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        if line.startswith("### "):
            current_section = line[4:].strip()
            continue

        if not line.startswith("- "):
            continue

        bullet = line[2:].strip()
        if not bullet:
            continue

        # Pattern format: - **P1 名称**：description
        m_pattern = re.match(r"\*{0,2}([A-Z]?\d+)\s+(.+?)\*{0,2}[：:]\s*(.*)", bullet)
        if m_pattern:
            pat_id = m_pattern.group(1)
            pat_name = m_pattern.group(2).strip()
            pat_desc = m_pattern.group(3).strip()
            # Check if description spans multiple lines
            items.append(KnowledgeItem(
                book_id=book_id,
                book_title=book_title,
                knowledge_level="Work-specific Pattern",
                dimension=current_section,
                text=f"[{pat_id} {pat_name}] {pat_desc}",
                source_file="knowledge/patterns.md",
                source_anchor=pat_id,
                evidence=[],
                confidence=None,
            ))
            continue

        # Numbered mechanism: 1. **名称**（ch_NNNN）：description
        m_mech = re.match(r"(\d+)\.\s+\*{0,2}(.+?)\*{0,2}（?([^）]*)）?[：:]\s*(.*)", bullet)
        if m_mech:
            mech_name = m_mech.group(2).strip()
            mech_ref = m_mech.group(3).strip()
            mech_desc = m_mech.group(4).strip()
            evidence = [mech_ref] if mech_ref else []
            items.append(KnowledgeItem(
                book_id=book_id,
                book_title=book_title,
                knowledge_level="Work-specific Pattern",
                dimension=current_section,
                text=f"[{mech_name}] {mech_desc}",
                source_file="knowledge/patterns.md",
                source_anchor=f"mech:{mech_name}",
                evidence=evidence,
                confidence=None,
            ))

    return items


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------

def parse_boundaries(bkp_dir: str, book_id: str, book_title: str) -> list:
    """Parse knowledge/boundaries.md into KnowledgeItems."""
    text = _read(Path(bkp_dir) / "knowledge" / "boundaries.md")
    if not text:
        return []

    items = []
    current_section = ""

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("## "):
            current_section = line[3:].strip()
            continue

        if line.startswith("### "):
            current_section = line[4:].strip()
            continue

        if not line.startswith("- "):
            continue

        bullet = line[2:].strip()
        # Remove [BOUNDARY] prefix
        bullet = re.sub(r"^\[BOUNDARY\]\s*", "", bullet).strip()
        if not bullet:
            continue

        if "｜证据：" in bullet or "|证据:" in bullet:
            evidence, confidence, clean_text = _extract_refs_pipe(bullet)
        else:
            evidence, confidence, _, _, clean_text = _extract_refs_paren(bullet)

        items.append(KnowledgeItem(
            book_id=book_id,
            book_title=book_title,
            knowledge_level="Boundary",
            dimension=current_section,
            text=clean_text if clean_text else bullet,
            source_file="knowledge/boundaries.md",
            source_anchor=f"boundary:{current_section}",
            evidence=evidence,
            confidence=confidence,
        ))

    return items


# ---------------------------------------------------------------------------
# Deep Dive
# ---------------------------------------------------------------------------

def parse_deep_dives(bkp_dir: str, book_id: str, book_title: str,
                     deep_dive_list: list) -> list:
    """Parse deep_dive/dd_*.md files into KnowledgeItems."""
    items = []
    bkp_path = Path(bkp_dir)

    for dd_info in deep_dive_list:
        dd_file = bkp_path / dd_info.get("file", "")
        if not dd_file.exists():
            continue

        text = _read(str(dd_file))
        if not text:
            continue

        dimension = dd_info.get("dimension", "")
        current_section = ""

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("## "):
                current_section = line[3:].strip()
                continue

            if not line.startswith("- "):
                continue

            bullet = line[2:].strip()
            if not bullet:
                continue

            # Skip metadata lines
            if bullet.startswith("维度/") or bullet.startswith("生成工具"):
                continue

            # Extract knowledge type from bullet
            kl = "Deep Dive Knowledge"
            clean = bullet

            if "[FACT]" in bullet:
                kl = "Deep Dive Evidence"
                clean = re.sub(r"\[FACT\]\s*", "", bullet)
            elif "[OBSERVATION]" in bullet:
                kl = "Deep Dive Observation"
                clean = re.sub(r"\[OBSERVATION\]\s*dimension:\S+\s*\|\s*", "", bullet)
                clean = re.sub(r"\[OBSERVATION\]\s*", "", clean)
            elif "[BOUNDARY]" in bullet:
                kl = "Deep Dive Boundary"
                clean = re.sub(r"\[BOUNDARY\]\s*", "", bullet)
            elif re.match(r"\*{0,2}[A-Z]?\d+\s+", bullet):
                kl = "Deep Dive Pattern"
                # Keep the full pattern text

            if "｜证据：" in clean or "|证据:" in clean:
                evidence, confidence, text_clean = _extract_refs_pipe(clean)
            else:
                evidence, confidence, _, _, text_clean = _extract_refs_paren(clean)

            items.append(KnowledgeItem(
                book_id=book_id,
                book_title=book_title,
                knowledge_level=kl,
                dimension=dimension,
                text=text_clean if text_clean else clean,
                source_file=dd_info.get("file", ""),
                source_anchor=f"dd:{dimension}/{current_section}",
                evidence=evidence,
                confidence=confidence,
                tags=[f"deep_dive:{dimension}"],
            ))

    return items


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_bkp(bkp_info: dict) -> list:
    """Load all knowledge items from a single BKP."""
    bkp_dir = bkp_info["bkp_dir"]
    book_id = bkp_info["book_id"]
    book_title = bkp_info["title"]
    identity = bkp_info["identity"]

    items = []
    items.extend(parse_observations(bkp_dir, book_id, book_title))
    items.extend(parse_inferences(bkp_dir, book_id, book_title))
    items.extend(parse_patterns(bkp_dir, book_id, book_title))
    items.extend(parse_boundaries(bkp_dir, book_id, book_title))

    deep_dives = identity.get("bkp_contents", {}).get("deep_dives", [])
    items.extend(parse_deep_dives(bkp_dir, book_id, book_title, deep_dives))

    return items
