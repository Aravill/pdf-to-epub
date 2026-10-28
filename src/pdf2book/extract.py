"""Turn a PDF into a format-neutral Book: metadata, chapters and paragraphs."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

# A line ending this many points before the right margin is treated as the
# last line of a paragraph.
SHORT_LINE_SLACK = 30
PAGE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")
# Text that can plausibly end a paragraph.
TERMINAL_RE = re.compile(r"[.!?:…”\"’)*]$")


@dataclass
class Chapter:
    title: str
    level: int = 1
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class Book:
    title: str
    author: str
    chapters: list[Chapter]
    cover_png: bytes | None = None
    page_count: int = 0
    # 0-based pages that hold images but no text (scans, illustrations).
    image_only_pages: list[int] = field(default_factory=list)
    from_bookmarks: bool = False


@dataclass
class _Line:
    text: str
    ends_paragraph: bool


def _page_lines(page: pymupdf.Page) -> list[_Line]:
    """Return the page's text lines, each flagged if it ends a paragraph."""
    blocks = page.get_text("dict")["blocks"]
    raw: list[list[tuple[str, float]]] = []
    for block in blocks:
        if block["type"] != 0:  # skip images
            continue
        lines = []
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text and not PAGE_NUMBER_RE.match(text):
                lines.append((text, line["bbox"][2]))
        if lines:
            raw.append(lines)

    if not raw:
        return []
    right_margin = max(x1 for block in raw for _, x1 in block)

    # A paragraph ends at a block boundary or a visibly short line, but only if
    # the line ends like a sentence; otherwise it continues (including onto
    # the next page).
    result = []
    for block in raw:
        for i, (text, x1) in enumerate(block):
            is_last = i == len(block) - 1
            short = x1 < right_margin - SHORT_LINE_SLACK
            ends = (is_last or short) and bool(TERMINAL_RE.search(text))
            result.append(_Line(text, ends_paragraph=ends))
    return result


def _join(prev: str, nxt: str) -> str:
    # Rejoin words hyphenated across a line break ("exam-" + "ple").
    if re.search(r"[A-Za-z]-$", prev) and nxt[:1].islower():
        return prev[:-1] + nxt
    return f"{prev} {nxt}"


def _paragraphs(doc: pymupdf.Document, start: int, end: int) -> list[str]:
    """Paragraphs from pages [start, end), 0-based."""
    paragraphs: list[str] = []
    current = ""
    for page_no in range(start, end):
        for line in _page_lines(doc[page_no]):
            current = _join(current, line.text) if current else line.text
            if line.ends_paragraph:
                paragraphs.append(current)
                current = ""
    if current:
        paragraphs.append(current)
    return paragraphs


def _strip_heading(paragraphs: list[str], title: str) -> None:
    """Drop the chapter heading the PDF already printed at the top of the chapter."""
    if paragraphs and paragraphs[0][: len(title)].casefold() == title.casefold():
        rest = paragraphs[0][len(title) :].strip()
        if rest:
            paragraphs[0] = rest
        else:
            paragraphs.pop(0)


def _render_cover(doc: pymupdf.Document) -> bytes:
    return doc[0].get_pixmap(dpi=150).tobytes("png")


def extract(pdf_path: Path, *, with_cover: bool = True) -> Book:
    doc = pymupdf.open(pdf_path)
    meta = doc.metadata or {}
    title = meta.get("title") or pdf_path.stem
    author = meta.get("author") or "Unknown"

    # Use the PDF's bookmarks as chapter boundaries when available.
    toc = [(lvl, name, page - 1) for lvl, name, page in doc.get_toc() if page >= 1]
    chapters: list[Chapter] = []
    if toc:
        if toc[0][2] > 0:
            toc.insert(0, (1, "Front matter", 0))
        for i, (level, name, start) in enumerate(toc):
            end = toc[i + 1][2] if i + 1 < len(toc) else doc.page_count
            paragraphs = _paragraphs(doc, start, max(start, end))
            _strip_heading(paragraphs, name.strip())
            chapters.append(Chapter(name.strip(), level, paragraphs))
        chapters = [c for c in chapters if c.paragraphs or c.title != "Front matter"]
    else:
        chapters.append(Chapter(title, 1, _paragraphs(doc, 0, doc.page_count)))

    image_only = [
        page.number
        for page in doc
        if not PAGE_NUMBER_RE.sub("", page.get_text()).strip() and page.get_images()
    ]
    cover = _render_cover(doc) if with_cover and doc.page_count else None
    return Book(title, author, chapters, cover, doc.page_count, image_only, bool(toc))
