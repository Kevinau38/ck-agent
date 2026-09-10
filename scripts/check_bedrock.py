"""Phase 0 acceptance check: confirm identity, agent model, and embedding model."""

import json
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION", "ap-southeast-1")
AGENT_MODEL = os.getenv("AGENT_MODEL_ID")
EMBED_MODEL = os.getenv("EMBED_MODEL_ID")

ok = True

ident = boto3.client("sts", region_name=REGION).get_caller_identity()
arn = ident["Arn"]
print(f"[1] Identity: {arn}")
if arn.endswith(":root"):
    print("    CANH BAO: dang chay bang root. Hay tao IAM user rieng.")
    ok = False
else:
    print("    OK - khong phai root.")

rt = boto3.client("bedrock-runtime", region_name=REGION)

try:
    r = rt.converse(
        modelId=AGENT_MODEL,
        messages=[{"role": "user", "content": [{"text": "reply with the word ok"}]}],
    )
    print(f"[2] Agent model OK: {r['output']['message']['content'][0]['text'].strip()}")
except Exception as e:
    print(f"[2] Agent model LOI: {e}")
    ok = False

try:
    body = {"texts": ["test"], "input_type": "search_document", "truncate": "END"}
    r = rt.invoke_model(modelId=EMBED_MODEL, body=json.dumps(body))
    dim = len(json.loads(r["body"].read())["embeddings"][0])
    print(f"[3] Embedding OK: {dim} chieu")
except Exception as e:
    print(f"[3] Embedding LOI: {e}")
    ok = False

print("\nSAN SANG." if ok else "\nCON VAN DE - xem o tren.")
sys.exit(0 if ok else 1)
