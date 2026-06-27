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

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    total INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    deadline_days INTEGER,
    created_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    upload_type TEXT NOT NULL,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL
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
        self._migrate()

    def _migrate(self) -> None:
        """Safe incremental migrations for existing databases."""
        with self.connect() as conn:
            # Add client_token column to orders if missing
            existing = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
            if "client_token" not in existing:
                conn.execute("ALTER TABLE orders ADD COLUMN client_token TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_token ON orders(client_token)"
            )

    def upsert_order(self, order: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO orders (
                    id, status, customer_name, customer_email, customer_phone,
                    contact_preference, project_type, area, requirements, budget,
                    total, stripe_session_id, stripe_payment_intent, created_at,
                    paid_at, raw_json, client_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    raw_json=excluded.raw_json,
                    client_token=COALESCE(orders.client_token, excluded.client_token)
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
                    order.get("clientToken"),
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

    def update_status(self, order_id: str, status: str) -> dict | None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                (status, order_id),
            )
            row = conn.execute("SELECT raw_json FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                return None
            order = json.loads(row["raw_json"])
            order["status"] = status
            conn.execute(
                "UPDATE orders SET raw_json = ? WHERE id = ?",
                (json.dumps(order, ensure_ascii=False), order_id),
            )
            return order

    def find_order_by_session(self, session_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT raw_json FROM orders WHERE stripe_session_id = ?", (session_id,)).fetchone()
            return json.loads(row["raw_json"]) if row else None

    def find_order_by_token(self, token: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT raw_json FROM orders WHERE client_token = ?", (token,)
            ).fetchone()
            return json.loads(row["raw_json"]) if row else None

    def get_order(self, order_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT raw_json FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            return json.loads(row["raw_json"]) if row else None

    def list_orders(self, skip: int = 0, limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT raw_json FROM orders ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, skip),
            ).fetchall()
            return [json.loads(row["raw_json"]) for row in rows]

    # ── Quotes ──────────────────────────────────────────────────

    def save_quote(self, order_id: str, total: int, notes: str, scope: str, deadline_days: int | None) -> dict:
        with self.connect() as conn:
            now = utcnow()
            cursor = conn.execute(
                """
                INSERT INTO quotes (order_id, total, notes, scope, deadline_days, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, total, notes, scope, deadline_days, now),
            )
            quote_id = cursor.lastrowid
            conn.execute(
                "UPDATE orders SET status = 'cotizado', total = ? WHERE id = ?",
                (total, order_id),
            )
            row = conn.execute("SELECT raw_json FROM orders WHERE id = ?", (order_id,)).fetchone()
            order = json.loads(row["raw_json"])
            order["status"] = "cotizado"
            order["total"] = total
            order["quote"] = {
                "id": quote_id,
                "total": total,
                "notes": notes,
                "scope": scope,
                "deadlineDays": deadline_days,
                "createdAt": now,
            }
            conn.execute(
                "UPDATE orders SET raw_json = ? WHERE id = ?",
                (json.dumps(order, ensure_ascii=False), order_id),
            )
            return order

    def mark_quote_sent(self, order_id: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE quotes SET sent_at = ?
                WHERE order_id = ? AND sent_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (utcnow(), order_id),
            )

    def get_latest_quote(self, order_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM quotes WHERE order_id = ? ORDER BY created_at DESC LIMIT 1",
                (order_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "orderId": row["order_id"],
                "total": row["total"],
                "notes": row["notes"],
                "scope": row["scope"],
                "deadlineDays": row["deadline_days"],
                "createdAt": row["created_at"],
                "sentAt": row["sent_at"],
            }

    # ── Uploads ─────────────────────────────────────────────────

    def save_upload(self, order_id: str, upload_type: str, original_name: str, stored_name: str, size_bytes: int) -> dict:
        with self.connect() as conn:
            now = utcnow()
            cursor = conn.execute(
                """
                INSERT INTO uploads (order_id, upload_type, original_name, stored_name, size_bytes, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, upload_type, original_name, stored_name, size_bytes, now),
            )
            return {
                "id": cursor.lastrowid,
                "orderId": order_id,
                "type": upload_type,
                "originalName": original_name,
                "storedName": stored_name,
                "sizeBytes": size_bytes,
                "uploadedAt": now,
            }

    def list_uploads(self, order_id: str, upload_type: str | None = None) -> list[dict]:
        with self.connect() as conn:
            if upload_type:
                rows = conn.execute(
                    "SELECT * FROM uploads WHERE order_id = ? AND upload_type = ? ORDER BY uploaded_at",
                    (order_id, upload_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM uploads WHERE order_id = ? ORDER BY upload_type, uploaded_at",
                    (order_id,),
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "orderId": r["order_id"],
                    "type": r["upload_type"],
                    "originalName": r["original_name"],
                    "storedName": r["stored_name"],
                    "sizeBytes": r["size_bytes"],
                    "uploadedAt": r["uploaded_at"],
                }
                for r in rows
            ]

    # ── Events & Emails ─────────────────────────────────────────

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
