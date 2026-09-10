"""Tool schemas for the Converse API, plus the dispatcher that runs them.

The Session object is the point of this module. Verification state lives here,
in Python, for the lifetime of one conversation. The model can ask to run a
tool; it cannot set `verified_user_id` itself, cannot read it, and cannot talk
its way past the guard clauses below. Prompt wording is advisory - these
checks are not.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from retrieval import format_context, search  # noqa: E402
from verify import get_shipment, list_orders, verify_user  # noqa: E402

NOT_VERIFIED = (
    "The user has not completed verification. Ask for their email address, "
    "full name, the last 4 digits of their SSN, and their date of birth. Do "
    "not reveal or imply any order information."
)


@dataclass
class Session:
    """Per-conversation state. Never serialised into the model context."""

    verified_user_id: str | None = None
    full_name: str | None = None
    failed_attempts: int = 0
    orders_listed: bool = False
    tool_calls: list[str] = field(default_factory=list)


TOOL_SPECS = [
    {
        "toolSpec": {
            "name": "search_documents",
            "description": (
                "Search the company's internal document library and return "
                "relevant passages with their page numbers. Use this for any "
                "question about the business, its risks, financials, "
                "properties, or stock. Always ground answers in what this "
                "returns and cite the page number."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The user's question, in English.",
                        }
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "verify_identity",
            "description": (
                "Verify a customer before any order information is discussed. "
                "Call this only once all four values have been collected from "
                "the user. Never guess or invent any of them."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "string",
                            "description": "Company email, e.g. name@ck1.com",
                        },
                        "full_name": {
                            "type": "string",
                            "description": "Full name on the account, as the user typed it.",
                        },
                        "ssn_last4": {
                            "type": "string",
                            "description": "SSN digits exactly as the user typed them.",
                        },
                        "date_of_birth": {
                            "type": "string",
                            "description": (
                                "Date of birth exactly as the user typed it, in "
                                "any format. Do not reformat it."
                            ),
                        },
                    },
                    "required": ["email", "full_name", "ssn_last4", "date_of_birth"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "list_my_orders",
            "description": (
                "List every order belonging to the verified customer. If more "
                "than one is returned, present all of them and ask the customer "
                "which one they mean. Never assume."
            ),
            "inputSchema": {"json": {"type": "object", "properties": {}}},
        }
    },
    {
        "toolSpec": {
            "name": "get_order_status",
            "description": (
                "Shipment status for one specific order belonging to the "
                "verified customer. Only call this after the customer has "
                "named which order they want."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Order ID the customer selected, e.g. ORD-10021",
                        }
                    },
                    "required": ["order_id"],
                }
            },
        }
    },
]


def _search_documents(session: Session, args: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "No query supplied."
    return format_context(search(query))


def _verify_identity(session: Session, args: dict) -> str:
    result = verify_user(
        args.get("email", ""),
        args.get("full_name", ""),
        args.get("ssn_last4", ""),
        args.get("date_of_birth", ""),
    )
    if not result["verified"]:
        session.failed_attempts += 1
        if session.failed_attempts >= 3:
            return (
                "Verification has failed three times. Stop asking for the "
                "details again and refer the customer to human support."
            )
        return f"Verification failed. {result['reason']}"

    session.verified_user_id = result["user_id"]
    session.full_name = result["full_name"]
    session.failed_attempts = 0
    return (
        f"Verification succeeded for {result['full_name']}. "
        "You may now look up their orders."
    )


def _list_my_orders(session: Session, args: dict) -> str:
    if not session.verified_user_id:
        return NOT_VERIFIED

    orders = list_orders(session.verified_user_id)
    if not orders:
        return "This customer has no orders on file."

    session.orders_listed = True
    lines = [f"{len(orders)} order(s) found:"]
    for o in orders:
        lines.append(
            f"- {o['order_id']} | placed {o['placed_at']} | "
            f"{o['summary']} | ${o['total_usd']:.2f}"
        )
    if len(orders) > 1:
        lines.append(
            "Present this list to the customer and ask which order they want. "
            "Do not pick one for them."
        )
    return "\n".join(lines)


def _get_order_status(session: Session, args: dict) -> str:
    if not session.verified_user_id:
        return NOT_VERIFIED

    # The brief forbids assuming which order the customer means. A model can
    # skip that step - it did in testing, reusing an ID the customer had
    # mentioned in passing - so the rule is enforced here instead of in the
    # prompt. One order is unambiguous, so it is allowed straight through.
    if not session.orders_listed and len(list_orders(session.verified_user_id)) > 1:
        return (
            "This customer has more than one order and has not been shown the "
            "list yet. Call list_my_orders, present every order to them, and "
            "ask which one they mean before checking any status."
        )

    order_id = (args.get("order_id") or "").strip().upper()
    row = get_shipment(session.verified_user_id, order_id)
    if row is None:
        # Same message whether the order does not exist or belongs to someone
        # else - the distinction would leak which IDs are real.
        return (
            f"No order {order_id} was found for this customer. Ask them to "
            "check the ID, or offer to list their orders again."
        )

    return (
        f"Order {row['order_id']} ({row['summary']}, ${row['total_usd']:.2f}, "
        f"placed {row['placed_at']})\n"
        f"Status: {row['status']}\n"
        f"Carrier: {row['carrier']}, tracking {row['tracking']}\n"
        f"Estimated delivery: {row['eta']}\n"
        f"Last updated: {row['updated_at']}"
    )


HANDLERS = {
    "search_documents": _search_documents,
    "verify_identity": _verify_identity,
    "list_my_orders": _list_my_orders,
    "get_order_status": _get_order_status,
}


def run_tool(session: Session, name: str, args: dict) -> str:
    session.tool_calls.append(name)
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}"
    try:
        return handler(session, args)
    except Exception as exc:  # surfaced to the model as a tool failure
        return f"Tool error: {type(exc).__name__}: {exc}"
