"""Two chunking strategies, kept side by side on purpose.

`chunk_naive`  - fixed-size character split over the raw text, no cleaning.
`chunk_smart`  - strips repeated page furniture, keeps tables whole, splits on
                 paragraph boundaries, and tags every chunk with its page number.

Building both lets us measure retrieval quality instead of asserting it.
That measurement is the deliverable for Level 300 item 5.
"""

from __future__ import annotations

import re

CHUNK_SIZE = 1000
OVERLAP = 150

# Every page of this filing starts with the same navigation line, and the
# company name repeats on most of them. Left in place, this boilerplate lands
# in every chunk and pulls unrelated chunks together in vector space.
BOILERPLATE = [
    re.compile(r"^\s*Table of Contents\s*$", re.IGNORECASE),
    re.compile(r"^\s*AMAZON\.COM,\s*INC\.\s*$", re.IGNORECASE),
    re.compile(r"^\s*FORM 10-K\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}\s*$"),  # bare page numbers
]


def clean_text(text: str) -> str:
    """Drop repeated page furniture and normalise whitespace."""
    kept = []
    for line in text.splitlines():
        line = line.replace("\u2022", "-").replace("\xa0", " ").rstrip()
        if any(p.match(line) for p in BOILERPLATE):
            continue
        kept.append(line)
    out = "\n".join(kept)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def split_fixed(text: str, size: int = CHUNK_SIZE, overlap: int = 0) -> list[str]:
    """Blind character-window split. Used by the naive strategy."""
    chunks = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(piece)
    return chunks


def split_paragraphs(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Accumulate whole paragraphs up to `size`, carrying a small tail over.

    Overlap matters because a risk factor often states the risk in one
    paragraph and its consequence in the next; a hard cut between them
    leaves both halves unanswerable.
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""

    for para in paras:
        if len(para) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(split_fixed(para, size, overlap))
            continue
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap else ""
            if tail:
                # start the carry-over at a word boundary, not mid-token
                cut = tail.find(" ")
                tail = tail[cut + 1 :] if cut != -1 else ""
            buf = f"{tail}\n\n{para}".strip() if tail else para

    if buf:
        chunks.append(buf)
    return chunks


def chunk_naive(pages: list[dict]) -> list[dict]:
    """Concatenate every page raw, then cut blindly every CHUNK_SIZE chars."""
    blob = "\n".join(p["text"] for p in pages)
    return [
        {"id": f"naive-{i}", "text": c, "page": None}
        for i, c in enumerate(split_fixed(blob, CHUNK_SIZE, 0))
    ]


def chunk_smart(pages: list[dict]) -> list[dict]:
    """Clean, keep tables atomic, split prose on paragraphs, tag page numbers.

    The page number is stored as a field, not written into the text. An early
    version prefixed every chunk with "[Page 17]", which put the same handful
    of tokens into all 117 vectors and measurably blunted broad queries. The
    number is still available at answer time - `format_context` attaches it
    when the passages are handed to the model - so nothing is lost by keeping
    it out of the embedding.
    """
    chunks: list[dict] = []

    for page in pages:
        page_no = page["page"]

        for j, table in enumerate(page.get("tables", [])):
            chunks.append(
                {
                    "id": f"smart-p{page_no}-t{j}",
                    "text": table,
                    "page": page_no,
                    "kind": "table",
                }
            )

        prose = clean_text(page["text"])
        if not prose:
            continue
        for j, piece in enumerate(split_paragraphs(prose)):
            chunks.append(
                {
                    "id": f"smart-p{page_no}-c{j}",
                    "text": piece,
                    "page": page_no,
                    "kind": "prose",
                }
            )

    return chunks
