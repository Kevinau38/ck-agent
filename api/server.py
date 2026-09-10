"""FastAPI wrapper around the agent.

The web layer is deliberately thin. All reasoning, verification and tool
dispatch already work through the CLI; this module only moves bytes. That
separation is why the interface can be swapped without touching any business
rule, and why a failure here cannot weaken verification.

Sessions live in a process dictionary, which is honest about what it is: fine
for a demo, wrong for production, where a restart must not log everyone out
and a second instance must see the same state. The write-up proposes
DynamoDB with a TTL for that.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from loop import stream_chat  # noqa: E402
from tools import Session  # noqa: E402

app = FastAPI(title="CK support agent")

SESSIONS: dict[str, tuple[Session, list[dict]]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "api" / "static" / "index.html")


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    session_id = req.session_id or str(uuid.uuid4())
    session, messages = SESSIONS.get(session_id, (Session(), []))

    def events():
        yield f"data: {json.dumps({'type': 'session', 'id': session_id})}\n\n"
        try:
            for kind, payload in stream_chat(req.message, messages, session):
                if kind == "done":
                    SESSIONS[session_id] = (session, payload)
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': kind, 'data': payload})}\n\n"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            yield f"data: {json.dumps({'type': 'error', 'data': error})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/reset")
def reset(req: ChatRequest) -> dict:
    """Drop a session. Used by the New chat button so a demo can restart
    verification from scratch without restarting the server."""
    if req.session_id:
        SESSIONS.pop(req.session_id, None)
    return {"ok": True}
