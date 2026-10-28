"""Write a Book to TXT, EPUB or MOBI."""

import html
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from ebooklib import epub

from .extract import Book


def write_txt(book: Book, out: Path) -> None:
    parts = [f"{book.title}\n{book.author}\n"]
    for chapter in book.chapters:
        parts.append(f"\n\n{chapter.title}\n{'=' * len(chapter.title)}\n")
        parts.extend(f"\n{p}\n" for p in chapter.paragraphs)
    out.write_text("".join(parts), encoding="utf-8")


def write_epub(book: Book, out: Path) -> None:
    eb = epub.EpubBook()
    eb.set_identifier(str(uuid.uuid4()))
    eb.set_title(book.title)
    eb.set_language("en")
    eb.add_author(book.author)
    if book.cover_png:
        eb.set_cover("cover.png", book.cover_png)

    items = []
    for i, chapter in enumerate(book.chapters, start=1):
        heading = min(chapter.level, 6)
        body = "".join(f"<p>{html.escape(p)}</p>" for p in chapter.paragraphs)
        item = epub.EpubHtml(title=chapter.title, file_name=f"chapter_{i:04d}.xhtml", lang="en")
        item.content = f"<h{heading}>{html.escape(chapter.title)}</h{heading}>{body}"
        eb.add_item(item)
        items.append(item)

    eb.toc = items
    eb.spine = ["nav", *items]
    eb.add_item(epub.EpubNcx())
    eb.add_item(epub.EpubNav())
    epub.write_epub(str(out), eb)


def write_mobi(book: Book, out: Path) -> None:
    # No maintained pure-Python MOBI writer exists; delegate to Calibre.
    converter = shutil.which("ebook-convert")
    if not converter:
        raise RuntimeError(
            "MOBI output needs Calibre's `ebook-convert` on PATH "
            "(e.g. `sudo pacman -S calibre`)."
        )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_epub = Path(tmp) / "book.epub"
        write_epub(book, tmp_epub)
        subprocess.run([converter, str(tmp_epub), str(out)], check=True, capture_output=True)


WRITERS = {"txt": write_txt, "epub": write_epub, "mobi": write_mobi}
