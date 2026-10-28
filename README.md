# pdf2book

Convert a PDF into TXT, EPUB or MOBI.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

MOBI output also needs Calibre's `ebook-convert` on your PATH (`sudo pacman -S calibre`).

## Usage

```sh
uv run pdf2book book.pdf                 # -> book.epub
uv run pdf2book book.pdf -f txt          # -> book.txt
uv run pdf2book book.pdf -f mobi         # -> book.mobi (needs Calibre)
uv run pdf2book book.pdf -o out/my.epub  # custom output path
uv run pdf2book book.pdf --no-cover      # don't use page 1 as the EPUB cover
```

## How it works

- `src/pdf2book/extract.py` reads the PDF with PyMuPDF and builds a format-neutral
  `Book` (title, author, chapters, paragraphs, cover image).
  - Chapters come from the PDF's bookmarks; without bookmarks the whole book is one chapter.
  - Lines are re-joined into paragraphs. A paragraph ends at a text block boundary or a
    short line, but only if the line ends like a sentence, so paragraphs flow across pages.
  - Bare page numbers are dropped, and hyphenated line breaks are rejoined.
- `src/pdf2book/writers.py` writes that `Book` as TXT, EPUB (via ebooklib), or MOBI
  (EPUB first, then Calibre's `ebook-convert`).

## Limitations

- Text only: images inside the book (other than the cover) are not carried over.
- Scanned PDFs (images of text) produce no text; OCR is not supported.
- Paragraph detection is heuristic, so oddly laid-out pages (poems, tables, title pages)
  may be merged or split imperfectly.
