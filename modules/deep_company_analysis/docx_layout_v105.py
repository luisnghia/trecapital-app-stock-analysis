from __future__ import annotations

"""V105 DOCX pagination hardening for Deep Company Analysis reports.

This module changes presentation-only OOXML pagination controls. It does not alter report
content, checklist state, canonical financial data, valuation/MOS, or investment decisions.
"""

from typing import Any, Iterator

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

LAYOUT_VERSION = "V105"


def _ensure_on_off(parent: Any, tag: str) -> bool:
    """Ensure an OOXML on/off child exists exactly once. Returns True when added."""
    name = qn(tag)
    if parent.find(name) is not None:
        return False
    element = OxmlElement(tag)
    element.set(qn("w:val"), "1")
    parent.append(element)
    return True


def _iter_tables(container: Any) -> Iterator[Any]:
    """Yield top-level and nested tables once each."""
    seen: set[int] = set()

    def walk(node: Any) -> Iterator[Any]:
        for table in getattr(node, "tables", ()):
            ident = id(table._tbl)
            if ident in seen:
                continue
            seen.add(ident)
            yield table
            for row in table.rows:
                for cell in row.cells:
                    yield from walk(cell)

    yield from walk(container)


def prevent_row_split(row: Any) -> bool:
    """Set w:cantSplit on a table row, idempotently."""
    tr_pr = row._tr.get_or_add_trPr()
    return _ensure_on_off(tr_pr, "w:cantSplit")


def repeat_header_row(row: Any) -> bool:
    """Set w:tblHeader on a table header row, idempotently."""
    tr_pr = row._tr.get_or_add_trPr()
    return _ensure_on_off(tr_pr, "w:tblHeader")


def keep_paragraph_with_next(paragraph: Any, *, keep_lines: bool = True) -> int:
    """Keep a heading with the content that follows it and avoid splitting its own lines."""
    p_pr = paragraph._p.get_or_add_pPr()
    added = int(_ensure_on_off(p_pr, "w:keepNext"))
    if keep_lines:
        added += int(_ensure_on_off(p_pr, "w:keepLines"))
    return added


def is_heading(paragraph: Any) -> bool:
    style = getattr(paragraph, "style", None)
    name = str(getattr(style, "name", "") or "").strip().lower()
    return name == "title" or name.startswith("heading")


def harden_document_layout(document: Any) -> dict[str, int]:
    """Apply deterministic pagination controls to a python-docx Document.

    - every table row receives ``w:cantSplit``;
    - the first row of every table receives ``w:tblHeader``;
    - Title/Heading paragraphs receive ``w:keepNext`` and ``w:keepLines``.

    The operation is intentionally idempotent because V101 -> V102 -> V103 composition may
    harden the same base document more than once.
    """
    stats = {
        "tables": 0,
        "rows": 0,
        "cant_split_added": 0,
        "header_rows": 0,
        "header_repeat_added": 0,
        "headings": 0,
        "heading_controls_added": 0,
    }

    for table in _iter_tables(document):
        stats["tables"] += 1
        for idx, row in enumerate(table.rows):
            stats["rows"] += 1
            stats["cant_split_added"] += int(prevent_row_split(row))
            if idx == 0:
                stats["header_rows"] += 1
                stats["header_repeat_added"] += int(repeat_header_row(row))

    for paragraph in document.paragraphs:
        if not is_heading(paragraph):
            continue
        stats["headings"] += 1
        stats["heading_controls_added"] += keep_paragraph_with_next(paragraph)

    return stats


__all__ = [
    "LAYOUT_VERSION",
    "harden_document_layout",
    "is_heading",
    "keep_paragraph_with_next",
    "prevent_row_split",
    "repeat_header_row",
]
