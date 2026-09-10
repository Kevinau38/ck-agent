# Retrieval comparison: naive vs preprocessed chunking

| Question | Naive top score | Smart top score | Smart pages cited |
| --- | --- | --- | --- |
| What are the main segments Amazon reports? | 0.590 | 0.572 | 3, 3, 3 |
| What competitive risks does Amazon disclose? | 0.549 | 0.511 | 8, 7, 6 |
| How much leased office square footage does Amazon have? | 0.615 | 0.642 | 16, 3, 16 |
| Where is Amazon common stock traded? | 0.555 | 0.638 | 17, 3, 1 |
| What were total net sales in the selected financial data? | 0.451 | 0.565 | 18, 3, 3 |
| What risks relate to international operations? | 0.646 | 0.612 | 7, 7, 10 |

Average top-1 cosine similarity: naive 0.568, smart 0.590.

The naive index cannot cite a page number at all, because concatenating the document before splitting discards the page boundary. Every smart chunk carries its page, so answers can be traced back to the filing.