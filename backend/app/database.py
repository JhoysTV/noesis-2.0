from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT,
    contact_preference TEXT,
    project_type TEXT NOT NULL,
    area TEXT,
    requirements TEXT,
    budget TEXT,
    total INTEGER NOT NULL,
    stripe_session_id TEXT UNIQUE,
    stripe_payment_intent TEXT,
    created_at TEXT NOT NULL,
    paid_at TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    catalog_item_id TEXT NOT NULL,
    name TEXT NOT NULL,
    price INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_events (
    stripe_event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    error TEXT
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_order(self, order: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO orders (
                    id, status, customer_name, customer_email, customer_phone,
                    contact_preference, project_type, area, requirements, budget,
                    total, stripe_session_id, stripe_payment_intent, created_at,
                    paid_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    customer_name=excluded.customer_name,
                    customer_email=excluded.customer_email,
                    customer_phone=excluded.customer_phone,
                    contact_preference=excluded.contact_preference,
                    project_type=excluded.project_type,
                    area=excluded.area,
                    requirements=excluded.requirements,
                    budget=excluded.budget,
                    total=excluded.total,
                    stripe_session_id=COALESCE(excluded.stripe_session_id, orders.stripe_session_id),
                    stripe_payment_intent=COALESCE(excluded.stripe_payment_intent, orders.stripe_payment_intent),
                    paid_at=COALESCE(excluded.paid_at, orders.paid_at),
                    raw_json=excluded.raw_json
                """,
                (
                    order["id"],
                    order["status"],
                    order["customer"]["name"],
                    order["customer"]["email"],
                    order["customer"].get("phone", ""),
                    order["customer"].get("contactPreference", ""),
                    order["projectType"],
                    order.get("area", ""),
                    order.get("requirements", ""),
                    order.get("budget", ""),
                    order["total"],
                    order.get("stripeSessionId"),
                    order.get("stripePaymentIntent"),
                    order["createdAt"],
                    order.get("paidAt"),
                    json.dumps(order, ensure_ascii=False),
                ),
            )
            conn.execute("DELETE FROM order_lines WHERE order_id = ?", (order["id"],))
            conn.executemany(
                """
                INSERT INTO order_lines (order_id, catalog_item_id, name, price)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (order["id"], item["id"], item["name"], item["price"])
                    for item in order["items"]
                ],
            )

    def set_checkout_session(self, order_id: str, session_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE orders SET stripe_session_id = ? WHERE id = ?",
                (session_id, order_id),
            )

    def mark_paid(self, order_id: str, session_id: str | None, payment_intent: str | None) -> dict | None:
        with self.connect() as conn:
            paid_at = utcnow()
            conn.execute(
                """
                UPDATE orders
                SET status = 'pagado',
                    paid_at = ?,
                    stripe_session_id = COALESCE(?, stripe_session_id),
                    stripe_payment_intent = COALESCE(?, stripe_payment_intent)
                WHERE id = ?
                """,
                (paid_at, session_id, payment_intent, order_id),
            )
            row = conn.execute("SELECT raw_json FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                return None
            order = json.loads(row["raw_json"])
            order["status"] = "pagado"
            order["paidAt"] = paid_at
            order["stripeSessionId"] = session_id or order.get("stripeSessionId")
            order["stripePaymentIntent"] = payment_intent or order.get("stripePaymentIntent")
            conn.execute("UPDATE orders SET raw_json = ? WHERE id = ?", (json.dumps(order, ensure_ascii=False), order_id))
            return order

    def find_order_by_session(self, session_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT raw_json FROM orders WHERE stripe_session_id = ?", (session_id,)).fetchone()
            return json.loads(row["raw_json"]) if row else None

    def list_orders(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT raw_json FROM orders ORDER BY created_at DESC").fetchall()
            return [json.loads(row["raw_json"]) for row in rows]

    def event_seen(self, event_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM payment_events WHERE stripe_event_id = ?", (event_id,)).fetchone()
            return bool(row)

    def record_event(self, event_id: str, event_type: str, payload: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO payment_events (stripe_event_id, event_type, processed_at, payload)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, event_type, utcnow(), payload),
            )

    def log_email(self, order_id: str, recipient: str, subject: str, status: str, error: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO email_logs (order_id, recipient, subject, status, created_at, error)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, recipient, subject, status, utcnow(), error),
            )
