"""Heuristic quality report for a conversion, so problems show up without
opening the result on an e-reader."""

import html
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ebooklib import ITEM_DOCUMENT, epub

from .extract import Book
from .writers import env_without_venv

OK, WARN, FAIL = "ok", "warn", "fail"
SYMBOLS = {OK: "✓", WARN: "!", FAIL: "✗"}
MAX_EXAMPLES = 3

# Words this long are almost always several words with the spaces missing.
GLUED_WORD_LEN = 21
GARBLED_RE = re.compile("[�-]")  # replacement + private-use chars
URLISH_RE = re.compile(r"/|www\.|\.(com|org|net|co\.uk)\b", re.IGNORECASE)


@dataclass
class Check:
    status: str
    message: str
    examples: list[str]


def _snippet(text: str, width: int = 60) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _pick(status_rules: list[tuple[bool, str]]) -> str:
    return next((status for cond, status in status_rules if cond), OK)


def _check_pages(book: Book) -> Check:
    n, total = len(book.image_only_pages), book.page_count
    share = n / total if total else 0
    status = _pick([(share > 0.5, FAIL), (share > 0.2, WARN)])
    msg = f"{total - n}/{total} pages have text"
    if n:
        msg += f"; {n} are images only"
        msg += " (scanned PDF? text in them is lost, OCR is not supported)" if status != OK else " (likely illustrations)"
    examples = [f"page {p + 1}" for p in book.image_only_pages[:MAX_EXAMPLES]] if status != OK else []
    return Check(status, msg, examples)


def _check_garbled(paras: list[tuple[str, str]]) -> Check:
    hits = [(t, p) for t, p in paras if GARBLED_RE.search(p)]
    total_chars = sum(len(p) for _, p in paras) or 1
    bad = sum(len(GARBLED_RE.findall(p)) for _, p in hits)
    status = _pick([(bad / total_chars > 0.01, FAIL), (bad > 0, WARN)])
    msg = "no garbled characters" if not bad else f"{bad} unreadable characters (broken font encoding)"
    return Check(status, msg, [f"{t}: {_snippet(p)}" for t, p in hits[:MAX_EXAMPLES]])


def _check_glued(paras: list[tuple[str, str]]) -> Check:
    hits, words = [], 0
    for title, p in paras:
        for w in p.split():
            words += 1
            letters = re.sub(r"\W", "", w)
            if len(letters) >= GLUED_WORD_LEN and not URLISH_RE.search(w):
                hits.append((title, w))
    status = _pick([(len(hits) / (words or 1) > 0.001, FAIL), (bool(hits), WARN)])
    msg = "no run-together words" if not hits else f"{len(hits)} run-together words (missing spaces)"
    return Check(status, msg, [f"{t}: {_snippet(w, 45)}" for t, w in hits[:MAX_EXAMPLES]])


def _check_breaks(paras: list[tuple[str, str]]) -> Check:
    # A paragraph starting in lowercase was almost certainly split mid-sentence.
    hits = [(t, p) for t, p in paras if p[:1].islower()]
    share = len(hits) / (len(paras) or 1)
    status = _pick([(share > 0.05, FAIL), (share > 0.005, WARN)])
    msg = f"{len(hits)} of {len(paras)} paragraphs start mid-sentence"
    examples = [f"{t}: {_snippet(p)}" for t, p in hits[:MAX_EXAMPLES]] if status != OK else []
    return Check(status, msg, examples)


def _check_merged(paras: list[tuple[str, str]]) -> Check:
    hits = [(t, p) for t, p in paras if len(p) > 5000]
    share = len(hits) / (len(paras) or 1)
    status = _pick([(share > 0.02, FAIL), (bool(hits), WARN)])
    msg = "no oversized paragraphs" if not hits else f"{len(hits)} oversized paragraphs (lines merged together?)"
    return Check(status, msg, [f"{t}: {len(p)} chars" for t, p in hits[:MAX_EXAMPLES]])


def _check_chapters(book: Book) -> Check:
    n = len(book.chapters)
    if not book.from_bookmarks:
        return Check(WARN, "PDF has no bookmarks, so the book is a single chapter with no table of contents", [])
    empty = [c.title for c in book.chapters if not c.paragraphs]
    msg = f"{n} chapters from PDF bookmarks"
    if empty:
        msg += f" ({len(empty)} without text, e.g. part dividers)"
    status = WARN if len(empty) > n / 2 else OK
    return Check(status, msg, empty[:MAX_EXAMPLES] if status != OK else [])


def _alnum_count(text: str) -> int:
    return sum(ch.isalnum() for ch in text)


def _read_back(out: Path, fmt: str) -> str | None:
    if fmt == "txt":
        return out.read_text(encoding="utf-8")
    if fmt == "epub":
        docs = epub.read_epub(str(out)).get_items_of_type(ITEM_DOCUMENT)
        raw = " ".join(d.get_content().decode("utf-8") for d in docs)
        return html.unescape(re.sub(r"<[^>]+>", " ", raw))
    if fmt == "mobi" and (converter := shutil.which("ebook-convert")):
        with tempfile.TemporaryDirectory() as tmp:
            txt = Path(tmp) / "back.txt"
            subprocess.run([converter, str(out), str(txt)], capture_output=True, env=env_without_venv())
            return txt.read_text(encoding="utf-8") if txt.exists() else ""
    return None


def _check_output(book: Book, out: Path, fmt: str) -> Check:
    expected = sum(_alnum_count(p) for c in book.chapters for p in c.paragraphs)
    try:
        text = _read_back(out, fmt)
    except Exception as e:  # any read failure means the file is broken
        return Check(FAIL, f"output file could not be read back: {e}", [])
    if text is None:
        return Check(WARN, "output file was not re-read (no reader available)", [])
    ratio = _alnum_count(text) / (expected or 1)
    status = _pick([(ratio < 0.9, FAIL), (ratio < 0.99, WARN)])
    return Check(status, f"output file holds {min(ratio, 1):.0%} of the extracted text", [])


def validate(book: Book, out: Path, fmt: str) -> list[Check]:
    paras = [(c.title, p) for c in book.chapters for p in c.paragraphs]
    return [
        _check_pages(book),
        _check_garbled(paras),
        _check_glued(paras),
        _check_breaks(paras),
        _check_merged(paras),
        _check_chapters(book),
        _check_output(book, out, fmt),
    ]


def format_report(checks: list[Check]) -> str:
    statuses = {c.status for c in checks}
    warnings = sum(c.status != OK for c in checks)
    if FAIL in statuses:
        verdict = "POOR: expect visible problems when reading"
    elif WARN in statuses:
        verdict = f"GOOD with {warnings} warning{'s' * (warnings > 1)}: worth a quick look"
    else:
        verdict = "GOOD: no problems detected"
    lines = [f"Quality check: {verdict}"]
    for c in checks:
        lines.append(f"  {SYMBOLS[c.status]} {c.message}")
        lines.extend(f"      e.g. {ex}" for ex in c.examples)
    return "\n".join(lines)
