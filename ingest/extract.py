"""Extract text and tables from the source PDF, one record per page.

The 10-K has a real text layer, so pdfplumber is enough - no OCR needed.
We keep tables separate from prose because they must never be split mid-row.
"""

from __future__ import annotations

import json
from pathlib import Path

import pdfplumber


def table_to_text(table: list[list[str | None]]) -> str:
    """Flatten a pdfplumber table into pipe-delimited lines.

    Keeping the header row attached to every table chunk is what stops the
    model from reading a number without knowing which column it came from.
    """
    rows = []
    for row in table:
        cells = [(c or "").replace("\n", " ").strip() for c in row]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def extract_pdf(pdf_path: str | Path) -> list[dict]:
    """Return [{page, text, tables}] for every page in the PDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Khong tim thay file PDF: {pdf_path}")

    pages: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables = [table_to_text(t) for t in (page.extract_tables() or [])]
            tables = [t for t in tables if t.strip()]
            pages.append({"page": i, "text": text, "tables": tables})
    return pages


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "data" / "Company-10k-18pages.pdf"
    out = root / "data" / "pages.json"

    pages = extract_pdf(src)
    out.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    n_tables = sum(len(p["tables"]) for p in pages)
    n_chars = sum(len(p["text"]) for p in pages)
    print(f"Da doc {len(pages)} trang, {n_chars} ky tu, {n_tables} bang.")
    for p in pages:
        if p["tables"]:
            print(f"  trang {p['page']}: {len(p['tables'])} bang")
    print(f"Ghi ra: {out}")


if __name__ == "__main__":
    main()
