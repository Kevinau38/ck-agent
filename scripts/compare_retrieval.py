"""Run the same questions against both indexes and write a comparison table.

This is the evidence for Level 300 item 5. The claim "preprocessing improves
retrieval" is worth little on its own; this script turns it into numbers and a
side-by-side of what each index actually returned.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from retrieval import search  # noqa: E402

# Questions chosen to span the document: business prose, risk factors,
# and the two numeric tables that naive chunking tends to break.
QUESTIONS = [
    "What are the main segments Amazon reports?",
    "What competitive risks does Amazon disclose?",
    "How much leased office square footage does Amazon have?",
    "Where is Amazon common stock traded?",
    "What were total net sales in the selected financial data?",
    "What risks relate to international operations?",
]


def run() -> list[dict]:
    rows = []
    for q in QUESTIONS:
        row = {"question": q}
        for variant in ("naive", "smart"):
            hits = search(q, k=3, variant=variant)
            row[variant] = {
                "top_score": hits[0]["score"] if hits else 0.0,
                "pages": [h.get("page") for h in hits],
                "preview": hits[0]["text"][:180].replace("\n", " ") if hits else "",
            }
        rows.append(row)
        print(
            f"{q[:52]:<52} naive={row['naive']['top_score']:.3f}  "
            f"smart={row['smart']['top_score']:.3f}"
        )
    return rows


def main() -> None:
    rows = run()

    out_json = ROOT / "docs" / "retrieval_comparison.json"
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Retrieval comparison: naive vs preprocessed chunking",
        "",
        "| Question | Naive top score | Smart top score | Smart pages cited |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        pages = ", ".join(str(p) for p in r["smart"]["pages"] if p)
        lines.append(
            f"| {r['question']} | {r['naive']['top_score']:.3f} | "
            f"{r['smart']['top_score']:.3f} | {pages} |"
        )

    n_avg = sum(r["naive"]["top_score"] for r in rows) / len(rows)
    s_avg = sum(r["smart"]["top_score"] for r in rows) / len(rows)
    lines += [
        "",
        f"Average top-1 cosine similarity: naive {n_avg:.3f}, smart {s_avg:.3f}.",
        "",
        "The naive index cannot cite a page number at all, because concatenating "
        "the document before splitting discards the page boundary. Every smart "
        "chunk carries its page, so answers can be traced back to the filing.",
    ]

    out_md = ROOT / "docs" / "retrieval_comparison.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDa ghi: {out_md}")


if __name__ == "__main__":
    main()
