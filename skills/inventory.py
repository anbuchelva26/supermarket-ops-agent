"""
Inventory skills for the Supermarket Ops Agent.

These tools provide the agent with grounded product, price, GST,
and stock information, as well as stock receiving operations.
"""

from __future__ import annotations

import sqlite3

from db.connection import get_connection, transaction


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a SQLite row into a normal Python dictionary."""
    return dict(row)


def search_products(query: str) -> list[dict]:
    """
    Search products by name using a case-insensitive partial match.

    Used by the agent to resolve product mentions such as
    "atta" or "rice" into actual products in the database.
    """
    if not query or not query.strip():
        return []

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM products
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY name ASC
            """,
            (f"%{query.strip()}%",),
        ).fetchall()

        return [_row_to_dict(row) for row in rows]

    finally:
        conn.close()


def get_product(product_id: int) -> dict:
    """
    Fetch a product by ID.

    Returns current price, stock, GST rate, HSN code,
    unit, and other product information.
    """
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"No product with id {product_id}")

        return _row_to_dict(row)

    finally:
        conn.close()


def add_product(
    name: str,
    unit: str,
    gst_rate: float,
    cost_price: float,
    sell_price: float,
    hsn_code: str | None = None,
    reorder_level: float = 0,
    is_loose: bool = False,
) -> dict:
    """
    Add a new product with zero initial stock.

    Product information is stored in the database. The agent should
    search for similar products before creating a new one.
    """

    if not name or not name.strip():
        raise ValueError("product name is required")

    if not unit or not unit.strip():
        raise ValueError("unit is required")

    if gst_rate < 0:
        raise ValueError("GST rate cannot be negative")

    if cost_price < 0:
        raise ValueError("cost price cannot be negative")

    if sell_price < 0:
        raise ValueError("sell price cannot be negative")

    if reorder_level < 0:
        raise ValueError("reorder level cannot be negative")

    conn = get_connection()

    try:
        cur = conn.execute(
            """
            INSERT INTO products
            (
                name,
                unit,
                is_loose,
                hsn_code,
                gst_rate,
                cost_price,
                sell_price,
                quantity,
                reorder_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                name.strip(),
                unit.strip(),
                int(is_loose),
                hsn_code,
                gst_rate,
                cost_price,
                sell_price,
                reorder_level,
            ),
        )

        new_id = cur.lastrowid

    finally:
        conn.close()

    return get_product(new_id)


def receive_stock(
    product_id: int,
    quantity: float,
    cost_price: float | None = None,
) -> dict:
    """
    Receive incoming stock for an existing product.

    The stock ledger entry and quantity update happen inside
    one database transaction so the operation cannot partially apply.

    If cost_price is provided, the product's current cost price
    is also updated.
    """

    if quantity <= 0:
        raise ValueError("quantity received must be positive")

    if cost_price is not None and cost_price < 0:
        raise ValueError("cost price cannot be negative")

    conn = get_connection()

    try:
        with transaction(conn):

            product = conn.execute(
                """
                SELECT id
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()

            if product is None:
                raise ValueError(
                    f"No product with id {product_id}"
                )

            # Record the stock movement.
            conn.execute(
                """
                INSERT INTO stock_ledger
                (
                    product_id,
                    change_qty,
                    reason
                )
                VALUES (?, ?, 'receive')
                """,
                (product_id, quantity),
            )

            # Increase stock and optionally update cost price.
            if cost_price is not None:
                conn.execute(
                    """
                    UPDATE products
                    SET
                        quantity = quantity + ?,
                        cost_price = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        quantity,
                        cost_price,
                        product_id,
                    ),
                )

            else:
                conn.execute(
                    """
                    UPDATE products
                    SET
                        quantity = quantity + ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        quantity,
                        product_id,
                    ),
                )

    finally:
        conn.close()

    return get_product(product_id)


def low_stock_report() -> list[dict]:
    """
    Return products whose quantity is at or below their reorder level.

    Results are ordered from lowest stock to highest stock.
    """
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM products
            WHERE quantity <= reorder_level
            ORDER BY quantity ASC
            """
        ).fetchall()

        return [_row_to_dict(row) for row in rows]

    finally:
        conn.close()