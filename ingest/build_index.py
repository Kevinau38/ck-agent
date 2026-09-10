"""Build two FAISS indexes - naive and smart - from data/pages.json.

Vectors are L2-normalised and stored in an inner-product index, which makes
the score cosine similarity. Cosine is the right measure here because chunk
length varies a lot (a table row versus a full paragraph) and raw dot product
would favour longer chunks.
"""

from __future__ import annotations

import json
from pathlib import Path

import sys

import faiss
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from chunk import chunk_naive, chunk_smart  # noqa: E402
from embed import embed_documents  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def build(name: str, chunks: list[dict]) -> None:
    print(f"\n[{name}] {len(chunks)} chunks")
    vectors = np.array(embed_documents([c["text"] for c in chunks]), dtype="float32")
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, str(DATA / f"index_{name}.faiss"))
    (DATA / f"chunks_{name}.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[{name}] xong - {vectors.shape[1]} chieu")


def main() -> None:
    pages = json.loads((DATA / "pages.json").read_text(encoding="utf-8"))
    build("naive", chunk_naive(pages))
    build("smart", chunk_smart(pages))
    print("\nDa build xong ca hai index.")


if __name__ == "__main__":
    main()
