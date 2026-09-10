"""Bedrock embedding client for cohere.embed-english-v3.

The single most important detail here: Cohere requires `input_type`, and it
must differ between indexing and querying. Passing `search_document` at query
time still returns vectors and still "works" - it just quietly retrieves worse
results. There is no error to catch, so it is encoded in the API below rather
than left to the caller to remember.
"""

from __future__ import annotations

import json
import os

import boto3

MODEL_ID = os.getenv("EMBED_MODEL_ID", "cohere.embed-english-v3")
REGION = os.getenv("AWS_REGION", "ap-southeast-1")

# Cohere accepts at most 96 texts per call.
BATCH = 90

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


def _invoke(texts: list[str], input_type: str) -> list[list[float]]:
    body = {"texts": texts, "input_type": input_type, "truncate": "END"}
    resp = client().invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["embeddings"]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed chunks for indexing."""
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        out.extend(_invoke(batch, "search_document"))
        print(f"  da embed {min(i + BATCH, len(texts))}/{len(texts)}")
    return out


def embed_query(text: str) -> list[float]:
    """Embed a user question for searching."""
    return _invoke([text], "search_query")[0]
