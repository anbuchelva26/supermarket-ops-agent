from __future__ import annotations

from db.connection import get_connection, transaction


def _get_customer_row(conn, customer_name: str):
    return conn.execute(
        """
        SELECT *
        FROM customers
        WHERE name = ? COLLATE NOCASE
        """,
        (customer_name.strip(),),
    ).fetchone()


def _create_customer_row(
    conn,
    customer_name: str,
    phone: str | None = None,
):
    cur = conn.execute(
        """
        INSERT INTO customers (name, phone, khata_balance)
        VALUES (?, ?, 0)
        """,
        (customer_name.strip(), phone),
    )

    return conn.execute(
        """
        SELECT *
        FROM customers
        WHERE id = ?
        """,
        (cur.lastrowid,),
    ).fetchone()


def _add_credit_txn(
    conn,
    customer_id: int,
    amount: float,
    note: str | None = None,
):
    """
    Add credit inside an existing database transaction.

    khata_ledger uses the sign of amount:
        positive = credit
        negative = payment
    """

    if amount <= 0:
        raise ValueError("credit amount must be positive")

    conn.execute(
        """
        INSERT INTO khata_ledger
        (customer_id, amount, note)
        VALUES (?, ?, ?)
        """,
        (customer_id, amount, note),
    )

    conn.execute(
        """
        UPDATE customers
        SET khata_balance = khata_balance + ?
        WHERE id = ?
        """,
        (amount, customer_id),
    )


def get_or_create_customer(
    customer_name: str,
    phone: str | None = None,
) -> dict:
    """Get an existing customer or create a new Khata customer."""

    if not customer_name or not customer_name.strip():
        raise ValueError("customer name is required")

    conn = get_connection()

    try:
        with transaction(conn):
            customer = _get_customer_row(conn, customer_name)

            if customer is None:
                customer = _create_customer_row(
                    conn,
                    customer_name,
                    phone,
                )

            return dict(customer)

    finally:
        conn.close()


def add_credit(
    customer_name: str,
    amount: float,
    note: str | None = None,
) -> dict:
    """
    Add an amount to a customer's outstanding Khata balance.

    A new customer may be created when adding credit.
    """

    if not customer_name or not customer_name.strip():
        raise ValueError("customer name is required")

    if amount <= 0:
        raise ValueError("credit amount must be positive")

    conn = get_connection()

    try:
        with transaction(conn):
            customer = _get_customer_row(conn, customer_name)

            if customer is None:
                customer = _create_customer_row(
                    conn,
                    customer_name,
                )

            _add_credit_txn(
                conn,
                customer["id"],
                amount,
                note,
            )

            updated = conn.execute(
                """
                SELECT *
                FROM customers
                WHERE id = ?
                """,
                (customer["id"],),
            ).fetchone()

            return dict(updated)

    finally:
        conn.close()


def record_payment(
    customer_name: str,
    amount: float,
    note: str | None = None,
) -> dict:
    """
    Record a payment against an existing Khata balance.

    A payment must NEVER create a customer automatically.
    """

    if not customer_name or not customer_name.strip():
        raise ValueError("customer name is required")

    if amount <= 0:
        raise ValueError("payment amount must be positive")

    conn = get_connection()

    try:
        with transaction(conn):
            customer = _get_customer_row(conn, customer_name)

            if customer is None:
                raise ValueError(
                    f"No khata exists for customer '{customer_name}'"
                )

            current_balance = float(customer["khata_balance"])

            if amount > current_balance:
                raise ValueError(
                    f"Payment ₹{amount:.2f} exceeds "
                    f"Khata balance ₹{current_balance:.2f}"
                )

            conn.execute(
                """
                INSERT INTO khata_ledger
                (customer_id, amount, note)
                VALUES (?, ?, ?)
                """,
                (
                    customer["id"],
                    -amount,
                    note or "payment",
                ),
            )

            conn.execute(
                """
                UPDATE customers
                SET khata_balance = khata_balance - ?
                WHERE id = ?
                """,
                (amount, customer["id"]),
            )

            updated = conn.execute(
                """
                SELECT *
                FROM customers
                WHERE id = ?
                """,
                (customer["id"],),
            ).fetchone()

            return dict(updated)

    finally:
        conn.close()


def get_balance(customer_name: str) -> dict:
    """Return the current Khata balance."""

    if not customer_name or not customer_name.strip():
        raise ValueError("customer name is required")

    conn = get_connection()

    try:
        customer = _get_customer_row(conn, customer_name)

        if customer is None:
            raise ValueError(
                f"No khata exists for customer '{customer_name}'"
            )

        return {
            "customer": customer["name"],
            "balance": float(customer["khata_balance"]),
        }

    finally:
        conn.close()