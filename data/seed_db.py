"""Create the mock order database.

Three tables in third normal form: a user has many orders, an order has one
shipment. This is a textbook OLTP shape - short lookups by key, joins along
foreign keys - which is why it is relational rather than a document store.
The conversation history, which is append-only and read by session, goes to
DynamoDB instead; two workloads, two stores.

All personal data here is synthetic. The SSNs are not valid numbers and the
emails use the fictional @ck<n>.com domains the assignment specifies.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "orders.db"

SCHEMA = """
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id    TEXT PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    full_name  TEXT NOT NULL,
    ssn_last4  TEXT NOT NULL,
    dob        TEXT NOT NULL
);

CREATE TABLE orders (
    order_id   TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(user_id),
    placed_at  TEXT NOT NULL,
    total_usd  REAL NOT NULL,
    summary    TEXT NOT NULL
);

CREATE TABLE shipments (
    shipment_id TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL UNIQUE REFERENCES orders(order_id),
    status      TEXT NOT NULL,
    carrier     TEXT NOT NULL,
    tracking    TEXT NOT NULL,
    eta         TEXT,
    updated_at  TEXT NOT NULL
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_users_email ON users(email);
"""

USERS = [
    ("U001", "jordan.reed@ck1.com", "Jordan Reed", "4821", "1990-01-05"),
    ("U002", "priya.nair@ck2.com", "Priya Nair", "0937", "1985-11-23"),
    ("U003", "sam.okafor@ck12.com", "Sam Okafor", "7150", "1998-07-04"),
    ("U004", "lena.novak@ck123.com", "Lena Novak", "3364", "1979-02-28"),
    ("U005", "marco.silva@ck7.com", "Marco Silva", "8802", "2001-09-16"),
]

ORDERS = [
    # Jordan Reed has three orders - this is the multi-order path the
    # assignment requires the agent to disambiguate rather than guess.
    ("ORD-10021", "U001", "2026-08-14", 129.99, "Wireless keyboard, 1x"),
    ("ORD-10088", "U001", "2026-08-29", 43.50, "USB-C cable 2m, 2x"),
    ("ORD-10154", "U001", "2026-09-03", 899.00, "27-inch monitor, 1x"),
    ("ORD-10047", "U002", "2026-08-19", 62.75, "Desk lamp, 1x"),
    ("ORD-10099", "U003", "2026-08-31", 215.40, "Office chair mat, 1x"),
    ("ORD-10112", "U003", "2026-09-01", 18.99, "Notebook pack, 3x"),
    ("ORD-10133", "U004", "2026-09-02", 1450.00, "Laptop dock and stand"),
    ("ORD-10160", "U005", "2026-09-05", 74.20, "Headphone stand, 1x"),
]

SHIPMENTS = [
    ("SHP-A1", "ORD-10021", "Delivered", "UPS", "1Z999AA10123456784",
     "2026-08-18", "2026-08-18"),
    ("SHP-A2", "ORD-10088", "In transit", "FedEx", "7712 3456 7890",
     "2026-09-12", "2026-09-09"),
    ("SHP-A3", "ORD-10154", "Preparing for shipment", "UPS", "PENDING",
     "2026-09-15", "2026-09-08"),
    ("SHP-B1", "ORD-10047", "Delivered", "USPS", "9400 1000 0000 0000 0000 00",
     "2026-08-23", "2026-08-23"),
    ("SHP-C1", "ORD-10099", "Out for delivery", "FedEx", "7712 9988 7766",
     "2026-09-10", "2026-09-10"),
    ("SHP-C2", "ORD-10112", "In transit", "USPS", "9400 1000 1111 2222 3333 44",
     "2026-09-13", "2026-09-09"),
    ("SHP-D1", "ORD-10133", "Delayed - weather", "UPS", "1Z999AA10987654321",
     "2026-09-16", "2026-09-09"),
    ("SHP-E1", "ORD-10160", "Preparing for shipment", "FedEx", "PENDING",
     "2026-09-14", "2026-09-08"),
]


def main() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO users VALUES (?,?,?,?,?)", USERS)
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", ORDERS)
    con.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?)", SHIPMENTS)
    con.commit()

    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("users", "orders", "shipments")
    }
    con.close()
    print(f"Da tao {DB}")
    print(f"  users={counts['users']} orders={counts['orders']} shipments={counts['shipments']}")
    print("  U001 (jordan.reed@ck1.com) co 3 don - dung de demo luong chon don")


if __name__ == "__main__":
    main()
