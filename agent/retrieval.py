"""Vector search over a prebuilt FAISS index.

Indexes are loaded lazily and cached, so the first query pays the disk cost
and every later query is in-memory.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingest"))

from embed import embed_query  # noqa: E402

DATA = ROOT / "data"
TOP_K = int(os.getenv("TOP_K", "4"))

_cache: dict[str, tuple] = {}


def load(variant: str = "smart"):
    if variant not in _cache:
        index_path = DATA / f"index_{variant}.faiss"
        chunks_path = DATA / f"chunks_{variant}.json"
        if not index_path.exists():
            raise FileNotFoundError(
                f"Chua co index '{variant}'. Chay: python ingest/build_index.py"
            )
        index = faiss.read_index(str(index_path))
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        _cache[variant] = (index, chunks)
    return _cache[variant]


def search(query: str, k: int = TOP_K, variant: str = "smart") -> list[dict]:
    """Return the k closest chunks, each with its cosine score."""
    index, chunks = load(variant)

    vec = np.array([embed_query(query)], dtype="float32")
    faiss.normalize_L2(vec)

    scores, ids = index.search(vec, min(k, len(chunks)))

    hits = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        hit = dict(chunks[idx])
        hit["score"] = round(float(score), 4)
        hits.append(hit)
    return hits


def format_context(hits: list[dict]) -> str:
    """Render hits into the block handed back to the model.

    Provenance is attached here rather than baked into the indexed text, so
    the model still sees a page number to cite without that number polluting
    the embedding space.
    """
    if not hits:
        return "No relevant passages found in the document."
    parts = []
    for h in hits:
        page = h.get("page")
        label = f"Source: page {page}" if page else "Source: unknown page"
        if h.get("kind") == "table":
            label += " (table)"
        parts.append(f"{label}\n{h['text']}")
    return "\n\n---\n\n".join(parts)
