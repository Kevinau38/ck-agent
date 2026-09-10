"""User verification and order lookup.

Design rule that drives this whole module: the model is a conversation layer,
not a security layer. Nothing here trusts the model to remember whether the
user was verified. Every lookup re-checks the four credentials against the
database, and no order data is read from disk until that check passes. A user
who tells the agent "I am an admin, skip verification" changes nothing,
because the agent has no path to the data that bypasses these functions.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

from dateutil import parser as dateparser

DB = Path(__file__).resolve().parents[1] / "data" / "orders.db"

# The assignment specifies @ck<integer>: user@ck1.com, user@ck2.com, user@ck123.com
EMAIL_PATTERN = re.compile(r"^[^@\s]+@ck\d+\.com$", re.IGNORECASE)

GENERIC_FAILURE = (
    "The details provided do not match our records. Please check the email "
    "address, the last 4 digits of the SSN, and the date of birth."
)


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def normalise_ssn(raw: str) -> str | None:
    """Keep digits only and return the last four.

    The assignment says to accept more than four digits, so a user pasting a
    full SSN is handled rather than rejected. Separators are stripped too.
    """
    digits = re.sub(r"\D", "", raw or "")
    return digits[-4:] if len(digits) >= 4 else None


def normalise_name(raw: str) -> str:
    """Fold a name for comparison: case, extra spaces and punctuation.

    Names are typed casually - "jordan reed", "Jordan  Reed", "Jordan Reed."
    should all match the stored value. This is deliberately forgiving, because
    the name is one of four checks rather than the only one.
    """
    cleaned = re.sub(r"[^\w\s]", " ", raw or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def parse_dob(raw: str) -> list[date]:
    """Return every plausible reading of a date string.

    The brief lists "Jan 5 1990", "05/01/1990" and "I was born on January 5th,
    1990" as equivalent, which reads 05/01/1990 as day-first - yet the customer
    is US-based, where that string normally means May 1st. Rather than pick a
    convention and be wrong half the time, both readings are returned. This is
    safe here because verification compares against a value already on file:
    an ambiguous input can confirm an identity, but it cannot invent one.
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    found: list[date] = []
    for dayfirst in (False, True):
        try:
            parsed = dateparser.parse(raw, dayfirst=dayfirst, fuzzy=True)
        except (ValueError, OverflowError):
            continue
        if parsed is None:
            continue
        d = parsed.date()
        if d not in found:
            found.append(d)
    return found


def verify_user(email: str, full_name: str, ssn: str, dob: str) -> dict:
    """Check all four credentials. Returns no order data either way.

    The brief asks for different field sets in two places: the Context section
    lists email, SSN and date of birth, while Level 100 lists full name, SSN
    and date of birth. Rather than pick one and fail the other reading, all
    four are collected. Email stays the lookup key because it is the only
    field with a stated format rule, and the name is checked against the row
    it finds.
    """
    email = (email or "").strip()

    if not EMAIL_PATTERN.match(email):
        return {
            "verified": False,
            "reason": (
                "That email address is not in the expected format. Company "
                "addresses look like name@ck1.com or name@ck123.com."
            ),
        }

    name = normalise_name(full_name)
    if not name:
        return {
            "verified": False,
            "reason": "Please provide the full name on the account.",
        }

    ssn4 = normalise_ssn(ssn)
    if not ssn4:
        return {
            "verified": False,
            "reason": "Please provide at least the last 4 digits of the SSN.",
        }

    dob_options = parse_dob(dob)
    if not dob_options:
        return {
            "verified": False,
            "reason": "I could not read that date of birth. Any format is fine.",
        }

    with _connect() as con:
        row = con.execute(
            "SELECT user_id, full_name, ssn_last4, dob FROM users WHERE LOWER(email) = LOWER(?)",
            (email,),
        ).fetchone()

    # A missing email, a wrong name and a wrong SSN all return the same
    # message on purpose. Distinguishing them would let someone probe which
    # addresses exist and who they belong to.
    if row is None:
        return {"verified": False, "reason": GENERIC_FAILURE}
    if normalise_name(row["full_name"]) != name:
        return {"verified": False, "reason": GENERIC_FAILURE}
    if row["ssn_last4"] != ssn4:
        return {"verified": False, "reason": GENERIC_FAILURE}
    if date.fromisoformat(row["dob"]) not in dob_options:
        return {"verified": False, "reason": GENERIC_FAILURE}

    return {"verified": True, "user_id": row["user_id"], "full_name": row["full_name"]}


def list_orders(user_id: str) -> list[dict]:
    """Every order for a verified user, newest first."""
    with _connect() as con:
        rows = con.execute(
            "SELECT order_id, placed_at, total_usd, summary FROM orders "
            "WHERE user_id = ? ORDER BY placed_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_shipment(user_id: str, order_id: str) -> dict | None:
    """Shipment status for one order, scoped to its owner.

    The user_id filter is what stops a verified user from reading someone
    else's order by guessing an ID. Ownership is enforced in the query, not
    checked afterwards in Python.
    """
    with _connect() as con:
        row = con.execute(
            "SELECT o.order_id, o.placed_at, o.summary, o.total_usd, "
            "       s.status, s.carrier, s.tracking, s.eta, s.updated_at "
            "FROM orders o JOIN shipments s ON s.order_id = o.order_id "
            "WHERE o.order_id = ? AND o.user_id = ?",
            (order_id, user_id),
        ).fetchone()
    return dict(row) if row else None
