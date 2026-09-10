# CK Agent — Solution Engineer Intern Assignment

Agentic conversational system for a US e-commerce company. Two capabilities:
RAG over an internal document, and an order-status workflow gated behind user
verification.

## Stack

| Layer | Choice |
| --- | --- |
| Agent loop | Bedrock Converse API + `toolConfig` |
| Model | Claude Haiku 4.5 via global inference profile |
| Embedding | `cohere.embed-english-v3` on Bedrock |
| Vector store | FAISS, local flat index |
| Order data | SQLite |
| Web layer | FastAPI + SSE streaming |
| Region | `ap-southeast-1` |

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

If PowerShell blocks the activate script, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Put the source PDF at `data\Company-10k-18pages.pdf`.

The virtual environment must be activated in every new terminal.

## Build (run once)

```powershell
python scripts\check_bedrock.py      # credentials, model access, embedding
python ingest\extract.py             # PDF to data\pages.json
python ingest\build_index.py         # build both FAISS indexes
python data\seed_db.py               # create the mock order database
```

`data\` holds generated artefacts and is gitignored, so a fresh clone must run
the three build steps above before the agent will start.

## Run

```powershell
python agent\loop.py                             # command line
python -m uvicorn api.server:app --reload --port 8000   # web at localhost:8000
```

## Test

```powershell
python scripts\test_verify.py        # 34 assertions on verification and access
python scripts\compare_retrieval.py  # retrieval quality, naive vs preprocessed
```

## Verification

Four credentials are collected before any order data is read: company email
matching `@ck<integer>`, full name, last 4 digits of SSN, and date of birth.

The brief specifies different field sets in two places, so all four are
collected to satisfy both readings. Email is the lookup key because it is the
only field with a stated format rule.

Values are accepted as typed. A full SSN is truncated to its last four digits
rather than rejected, and a date of birth is read in any format including a
sentence. Where a date is ambiguous, both readings are tried and either may
match, which is safe because verification compares against a value already on
file.

Verification state lives in `Session` in Python, never in the model context.
Every tool re-checks it, so no prompt wording can bypass a check.

## Why two indexes

`index_naive` splits the raw document on a fixed character window.
`index_smart` strips repeated page furniture, keeps tables whole, splits on
paragraph boundaries, and tags every chunk with its page number.

Both are built so retrieval quality can be measured rather than asserted.
See `docs\retrieval_comparison.md`.

## Cost

Everything runs locally except Bedrock calls, which are billed per token.
Nothing runs on a schedule and nothing is billed hourly.
