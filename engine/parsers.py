"""Multimodal document parsers for Axiom (PRD §4.3 A-04).

Converts input documents (Markdown, plain text, and future PDF/DOCX/image formats)
into structured ContentUnits with character offsets, normalized bounding boxes,
and kind tags.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from contracts.models import BBox, ContentUnit

try:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
    _HAS_MARKDOWN_IT = True
except ImportError:
    _HAS_MARKDOWN_IT = False


def parse_markdown(text: str, revision_id: str = "rev_default") -> List[ContentUnit]:
    """Parse a Markdown document into a sequence of ContentUnits.

    Tracks character offsets [start, end] accurately against the raw input text.
    Classifies elements into kind: "heading", "paragraph", "list_item", "code_block".
    """
    if not text.strip():
        return []

    units: List[ContentUnit] = []
    unit_counter = 1

    # If markdown-it-py is available, we can parse structured AST tokens,
    # but we need exact character offsets in the original raw text.
    # A robust regex/line-based scanner gives exact start/end offsets.
    
    # Normalize line breaks for offset consistency
    lines = text.split("\n")
    current_offset = 0
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        line_stripped = line.strip()

        if not line_stripped:
            current_offset += len(line) + 1  # +1 for newline
            i += 1
            continue

        # Check for heading (# Heading)
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            start = current_offset
            end = start + len(line)
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            
            unit = ContentUnit(
                unit_id=f"u_{unit_counter:03d}",
                revision_id=revision_id,
                kind="heading",
                text=line,
                start=start,
                end=end,
                page=1,
                bbox=BBox(page=1, x0=0.05, y0=0.05, x1=0.95, y1=0.10),
                style={"level": level, "heading": True},
            )
            units.append(unit)
            unit_counter += 1
            current_offset += len(line) + 1
            i += 1
            continue

        # Check for blockquote or list item or normal paragraph
        # Accumulate contiguous non-blank lines into a paragraph
        para_start = current_offset
        para_lines = [line]
        para_len = len(line)
        i += 1
        current_offset += len(line) + 1

        while i < n and lines[i].strip():
            # Check if next line is a new heading
            if re.match(r"^#{1,6}\s+", lines[i]):
                break
            para_lines.append(lines[i])
            para_len += 1 + len(lines[i])
            current_offset += len(lines[i]) + 1
            i += 1

        para_text = "\n".join(para_lines)
        para_end = para_start + len(para_text)

        kind = "paragraph"
        if para_lines[0].strip().startswith(("- ", "* ", "1. ")):
            kind = "list_item"
        elif para_lines[0].strip().startswith(">"):
            kind = "blockquote"

        unit = ContentUnit(
            unit_id=f"u_{unit_counter:03d}",
            revision_id=revision_id,
            kind=kind,
            text=para_text,
            start=para_start,
            end=para_end,
            page=1,
            bbox=BBox(page=1, x0=0.05, y0=0.10, x1=0.95, y1=0.25),
            style={"kind": kind},
        )
        units.append(unit)
        unit_counter += 1

    return units


def parse_text(text: str, revision_id: str = "rev_default") -> List[ContentUnit]:
    """Parse plain text into paragraph ContentUnits with exact offsets."""
    if not text.strip():
        return []

    units: List[ContentUnit] = []
    unit_counter = 1

    # Split by double newlines or single paragraphs
    paragraphs = re.split(r"(\n\s*\n)", text)
    current_offset = 0

    for part in paragraphs:
        if re.match(r"^\n\s*\n$", part) or not part.strip():
            current_offset += len(part)
            continue

        start = current_offset
        end = start + len(part)
        unit = ContentUnit(
            unit_id=f"u_{unit_counter:03d}",
            revision_id=revision_id,
            kind="paragraph",
            text=part.strip(),
            start=start,
            end=end,
            page=1,
            bbox=BBox(page=1, x0=0.05, y0=0.10, x1=0.95, y1=0.30),
        )
        units.append(unit)
        unit_counter += 1
        current_offset += len(part)

    return units


def parse_pdf_stub(file_bytes: bytes, revision_id: str = "rev_default") -> List[ContentUnit]:
    """PDF parser stub (G2). Returns char boxes, font info, and page bbox."""
    # Extensible for PyMuPDF in Issue #8/10
    return []


def parse_docx_stub(file_bytes: bytes, revision_id: str = "rev_default") -> List[ContentUnit]:
    """DOCX parser stub (G3)."""
    return []


def parse_image_stub(file_bytes: bytes, revision_id: str = "rev_default") -> List[ContentUnit]:
    """OCR image parser stub (G3)."""
    return []

