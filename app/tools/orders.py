import os
from typing import Optional

import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Hard business rule, enforced in code — never left to the LLM's judgment.
AUTO_APPROVE_REFUND_LIMIT = 50.00


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def ensure_schema_and_seed():
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_email TEXT NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                charge_date DATE NOT NULL,
                status TEXT NOT NULL DEFAULT 'charged'
            );
        """)
        cur.execute("SELECT COUNT(*) FROM orders;")
        count = cur.fetchone()[0]
        if count == 0:
            cur.execute("""
                INSERT INTO orders (order_id, customer_email, amount, charge_date, status) VALUES
                ('ORD-1001', 'alice@example.com', 15.00, '2026-09-01', 'charged'),
                ('ORD-1002', 'bob@example.com', 75.00, '2026-09-02', 'charged'),
                ('ORD-1003', 'carol@example.com', 5.00, '2026-08-20', 'refunded');
            """)
    conn.commit()
    conn.close()


def get_order(order_id: str) -> Optional[dict]:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT order_id, customer_email, amount, charge_date, status "
            "FROM orders WHERE order_id = %s",
            (order_id,),
        )
        row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "order_id": row[0],
        "customer_email": row[1],
        "amount": float(row[2]),
        "charge_date": str(row[3]),
        "status": row[4],
    }


def initiate_refund(order_id: str, amount: float) -> dict:
    """Marks an order as refund-pending or refunded, based on the hard
    auto-approve threshold. Returns the updated order plus whether it
    needed human approval."""
    requires_approval = amount >= AUTO_APPROVE_REFUND_LIMIT
    new_status = "refund_pending_approval" if requires_approval else "refunded"

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE orders SET status = %s WHERE order_id = %s",
            (new_status, order_id),
        )
    conn.commit()
    conn.close()

    return {
        "order_id": order_id,
        "refund_amount": amount,
        "new_status": new_status,
        "requires_human_approval": requires_approval,
    }
