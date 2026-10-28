import argparse
import sys
from pathlib import Path

from .extract import extract
from .writers import WRITERS


def main() -> None:
    parser = argparse.ArgumentParser(prog="pdf2book", description="Convert a PDF to TXT, EPUB or MOBI.")
    parser.add_argument("pdf", type=Path, help="input PDF file")
    parser.add_argument("-f", "--format", choices=WRITERS, default="epub", help="output format (default: epub)")
    parser.add_argument("-o", "--output", type=Path, help="output file (default: input name with new extension)")
    parser.add_argument("--no-cover", action="store_true", help="don't use the first page as the cover image")
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"no such file: {args.pdf}")
    out = args.output or args.pdf.with_suffix(f".{args.format}")

    book = extract(args.pdf, with_cover=not args.no_cover and args.format != "txt")
    try:
        WRITERS[args.format](book, out)
    except RuntimeError as e:
        sys.exit(f"error: {e}")
    print(f"Wrote {out} ({len(book.chapters)} chapters)")


if __name__ == "__main__":
    main()
