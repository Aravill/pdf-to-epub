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
uv run pdf2book book.pdf --no-check      # skip the quality report
```

## Quality report

After converting, a quick heuristic report gives a first verdict without opening the
book on an e-reader:

```
Quality check: GOOD with 1 warning: worth a quick look
  ✓ 942/1027 pages have text; 85 are images only (likely illustrations)
  ✓ no garbled characters
  ! 8 run-together words (missing spaces)
      e.g. ABOUT THE AUTHOR: SenLinYugrewupinthePacificNorthwestandstudie…
  ✓ 6 of 12662 paragraphs start mid-sentence
  ✓ no oversized paragraphs
  ✓ 89 chapters from PDF bookmarks (3 without text, e.g. part dividers)
  ✓ output file holds 100% of the extracted text
```

| Check | Catches |
|---|---|
| pages have text | scanned PDFs (image-only pages; their text is lost) |
| garbled characters | broken font encodings (`�` and private-use glyphs) |
| run-together words | PDFs that omit spaces between words |
| paragraphs start mid-sentence | paragraphs wrongly split in two |
| oversized paragraphs | many paragraphs wrongly merged into one |
| chapters | missing bookmarks (no table of contents) |
| output file | the written file can be read back and contains all the text (MOBI uses Calibre) |

It is a preliminary check, not proof: it can't see subtler issues such as a stray space
inside a word ("pr omise") or a heading glued to the first sentence.

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
