"""
Billing skill.

Covers:
- multi-turn bill building
- GST calculation
- stock validation
- oversell protection
- atomic stock decrement
- Cash / UPI / Card / Khata payments
- Khata credit integration
- finalize-time idempotency

A bill is stored in the database as a draft from the moment it is
started. Conversation state does not need to reconstruct the bill.
"""

from __future__ import annotations

import json
import sqlite3

from db.connection import get_connection, transaction
from skills import inventory
from skills.khata import (
    _get_customer_row,
    _create_customer_row,
    _add_credit_txn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _fetch_bill(
    conn: sqlite3.Connection,
    bill_id: int,
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT *
        FROM bills
        WHERE id = ?
        """,
        (bill_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"No bill with id {bill_id}")

    return row


def _fetch_items(
    conn: sqlite3.Connection,
    bill_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            bi.*,
            p.name AS product_name
        FROM bill_items bi
        JOIN products p
            ON p.id = bi.product_id
        WHERE bi.bill_id = ?
        ORDER BY bi.id
        """,
        (bill_id,),
    ).fetchall()


def _draft_bill_dict(
    conn: sqlite3.Connection,
    bill_id: int,
) -> dict:
    bill = _row_to_dict(
        _fetch_bill(conn, bill_id)
    )

    items = [
        _row_to_dict(row)
        for row in _fetch_items(conn, bill_id)
    ]

    bill["items"] = items

    bill["estimated_total"] = round(
        sum(item["line_total"] for item in items),
        2,
    )

    return bill


# ---------------------------------------------------------------------------
# Draft bill building
# ---------------------------------------------------------------------------

def start_bill(
    customer_id: int | None = None,
) -> dict:
    """
    Create a new draft bill.
    """

    conn = get_connection()

    try:
        cur = conn.execute(
            """
            INSERT INTO bills (
                status,
                customer_id
            )
            VALUES (
                'draft',
                ?
            )
            """,
            (customer_id,),
        )

        bill_id = cur.lastrowid

        return _draft_bill_dict(
            conn,
            bill_id,
        )

    finally:
        conn.close()


def add_line_item(
    bill_id: int,
    product_id: int,
    quantity: float,
) -> dict:
    """
    Add quantity of a product to a draft bill.

    If the product already exists on the bill, its quantity is increased.

    The current sell price and GST rate are snapshotted when the product
    is first added.
    """

    if quantity <= 0:
        raise ValueError("quantity must be positive")

    conn = get_connection()

    try:
        bill = _fetch_bill(
            conn,
            bill_id,
        )

        if bill["status"] != "draft":
            raise ValueError(
                f"Bill {bill_id} is not a draft "
                f"(status={bill['status']})"
            )

        product = inventory.get_product(
            product_id
        )

        existing = conn.execute(
            """
            SELECT *
            FROM bill_items
            WHERE bill_id = ?
              AND product_id = ?
            """,
            (
                bill_id,
                product_id,
            ),
        ).fetchone()

        if existing is None:

            unit_price = product["sell_price"]
            gst_rate = product["gst_rate"]

            line_total = round(
                unit_price * quantity,
                2,
            )

            conn.execute(
                """
                INSERT INTO bill_items (
                    bill_id,
                    product_id,
                    quantity,
                    unit_price,
                    gst_rate,
                    line_total
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    bill_id,
                    product_id,
                    quantity,
                    unit_price,
                    gst_rate,
                    line_total,
                ),
            )

        else:

            new_qty = (
                existing["quantity"]
                + quantity
            )

            new_total = round(
                existing["unit_price"] * new_qty,
                2,
            )

            conn.execute(
                """
                UPDATE bill_items
                SET
                    quantity = ?,
                    line_total = ?
                WHERE id = ?
                """,
                (
                    new_qty,
                    new_total,
                    existing["id"],
                ),
            )

        return _draft_bill_dict(
            conn,
            bill_id,
        )

    finally:
        conn.close()


def set_line_item_quantity(
    bill_id: int,
    product_id: int,
    quantity: float,
) -> dict:
    """
    Set an absolute quantity for an existing bill item.

    quantity=0 removes the item.
    """

    if quantity < 0:
        raise ValueError(
            "quantity cannot be negative"
        )

    conn = get_connection()

    try:
        bill = _fetch_bill(
            conn,
            bill_id,
        )

        if bill["status"] != "draft":
            raise ValueError(
                f"Bill {bill_id} is not a draft "
                f"(status={bill['status']})"
            )

        existing = conn.execute(
            """
            SELECT *
            FROM bill_items
            WHERE bill_id = ?
              AND product_id = ?
            """,
            (
                bill_id,
                product_id,
            ),
        ).fetchone()

        if existing is None:

            if quantity == 0:
                return _draft_bill_dict(
                    conn,
                    bill_id,
                )

            return add_line_item(
                bill_id,
                product_id,
                quantity,
            )

        if quantity == 0:

            conn.execute(
                """
                DELETE FROM bill_items
                WHERE id = ?
                """,
                (existing["id"],),
            )

        else:

            new_total = round(
                existing["unit_price"] * quantity,
                2,
            )

            conn.execute(
                """
                UPDATE bill_items
                SET
                    quantity = ?,
                    line_total = ?
                WHERE id = ?
                """,
                (
                    quantity,
                    new_total,
                    existing["id"],
                ),
            )

        return _draft_bill_dict(
            conn,
            bill_id,
        )

    finally:
        conn.close()


def remove_line_item(
    bill_id: int,
    product_id: int,
) -> dict:
    """
    Remove a product completely from a draft bill.
    """

    return set_line_item_quantity(
        bill_id,
        product_id,
        0,
    )


def get_draft_bill(
    bill_id: int,
) -> dict:
    """
    Return the current bill and its items.
    """

    conn = get_connection()

    try:
        return _draft_bill_dict(
            conn,
            bill_id,
        )

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GST
# ---------------------------------------------------------------------------

def _compute_gst_breakup(
    items: list[sqlite3.Row],
) -> dict:
    """
    Calculate GST from GST-inclusive retail prices.

    Example:

        Gross = ₹105
        GST   = 5%

        Taxable value = ₹100
        GST           = ₹5
        CGST          = ₹2.50
        SGST          = ₹2.50

    GST is calculated per line and rounded to paise.
    """

    subtotal = 0.0
    cgst_total = 0.0
    sgst_total = 0.0

    for item in items:

        gst_rate = item["gst_rate"]

        gross = (
            item["unit_price"]
            * item["quantity"]
        )

        if gst_rate:

            base = gross / (
                1 + gst_rate / 100
            )

        else:

            base = gross

        base = round(
            base,
            2,
        )

        tax = round(
            gross - base,
            2,
        )

        half_tax = round(
            tax / 2,
            2,
        )

        subtotal += base
        cgst_total += half_tax

        # Any odd paisa goes to SGST so:
        #
        # subtotal + CGST + SGST
        #
        # exactly equals the gross amount.
        sgst_total += (
            tax - half_tax
        )

    subtotal = round(
        subtotal,
        2,
    )

    cgst_total = round(
        cgst_total,
        2,
    )

    sgst_total = round(
        sgst_total,
        2,
    )

    grand_total = round(
        subtotal
        + cgst_total
        + sgst_total,
        2,
    )

    return {
        "subtotal": subtotal,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "grand_total": grand_total,
    }


# ---------------------------------------------------------------------------
# Finalize bill
# ---------------------------------------------------------------------------

_SUPPORTED_PAYMENT_MODES = {
    "cash",
    "upi",
    "card",
    "khata",
}


def finalize_bill(
    bill_id: int,
    payment_mode: str,
    idempotency_key: str,
    payment_ref: str | None = None,
    customer_name: str | None = None,
) -> dict:
    """
    Finalize a draft bill.

    Supported payment modes:

        cash
        upi
        card
        khata

    Khata behavior:

        - customer_name is required
        - customer is created if it does not exist
        - grand_total is added to the customer's Khata balance
        - bills.customer_id is populated

    Atomicity:

        Stock decrement, Khata credit, bill finalization and
        idempotency record happen inside one transaction.

    Idempotency:

        The same idempotency key returns the original result and
        does not perform the transaction again.

    Oversell protection:

        Stock is checked immediately before decrementing while the
        SQLite write transaction is active.
    """

    # ---------------------------------------------------------------
    # Normalize payment mode
    # ---------------------------------------------------------------

    if not payment_mode:
        raise ValueError(
            "payment_mode is required"
        )

    payment_mode = (
        payment_mode
        .strip()
        .lower()
    )

    if payment_mode not in _SUPPORTED_PAYMENT_MODES:
        raise ValueError(
            f"Unsupported payment mode "
            f"'{payment_mode}'. "
            f"Use one of "
            f"{sorted(_SUPPORTED_PAYMENT_MODES)}"
        )

    # ---------------------------------------------------------------
    # Khata requires customer
    # ---------------------------------------------------------------

    if payment_mode == "khata":

        if (
            not customer_name
            or not customer_name.strip()
        ):
            raise ValueError(
                "customer_name is required "
                "when payment_mode is 'khata'"
            )

        customer_name = customer_name.strip()

    # ---------------------------------------------------------------
    # Idempotency key validation
    # ---------------------------------------------------------------

    if (
        not idempotency_key
        or not idempotency_key.strip()
    ):
        raise ValueError(
            "idempotency_key is required"
        )

    idempotency_key = (
        idempotency_key.strip()
    )

    conn = get_connection()

    try:

        with transaction(conn):

            # -------------------------------------------------------
            # 1. Idempotency check
            # -------------------------------------------------------

            already = conn.execute(
                """
                SELECT result_summary
                FROM idempotency_keys
                WHERE key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if already is not None:

                return json.loads(
                    already["result_summary"]
                )

            # -------------------------------------------------------
            # 2. Fetch bill
            # -------------------------------------------------------

            bill = _fetch_bill(
                conn,
                bill_id,
            )

            if bill["status"] != "draft":

                raise ValueError(
                    f"Bill {bill_id} is not a draft "
                    f"(status={bill['status']})"
                )

            items = _fetch_items(
                conn,
                bill_id,
            )

            if not items:

                raise ValueError(
                    f"Bill {bill_id} has no "
                    f"line items to finalize"
                )

            # -------------------------------------------------------
            # 3. Oversell guard
            # -------------------------------------------------------

            for item in items:

                stock_row = conn.execute(
                    """
                    SELECT quantity
                    FROM products
                    WHERE id = ?
                    """,
                    (item["product_id"],),
                ).fetchone()

                if (
                    stock_row is None
                    or stock_row["quantity"]
                    < item["quantity"]
                ):

                    have = (
                        stock_row["quantity"]
                        if stock_row
                        else 0
                    )

                    raise ValueError(
                        f"Not enough "
                        f"{item['product_name']} "
                        f"in stock: "
                        f"have {have}, "
                        f"need {item['quantity']}"
                    )

            # -------------------------------------------------------
            # 4. Calculate GST
            # -------------------------------------------------------

            breakup = (
                _compute_gst_breakup(
                    items
                )
            )

            # -------------------------------------------------------
            # 5. Resolve Khata customer
            # -------------------------------------------------------

            customer_id = None

            if payment_mode == "khata":

                customer = (
                    _get_customer_row(
                        conn,
                        customer_name,
                    )
                )

                if customer is None:

                    customer = (
                        _create_customer_row(
                            conn,
                            customer_name,
                        )
                    )

                customer_id = customer["id"]

            # -------------------------------------------------------
            # 6. Decrement stock
            # -------------------------------------------------------

            for item in items:

                conn.execute(
                    """
                    INSERT INTO stock_ledger (
                        product_id,
                        change_qty,
                        reason,
                        reference_id
                    )
                    VALUES (
                        ?,
                        ?,
                        'sale',
                        ?
                    )
                    """,
                    (
                        item["product_id"],
                        -item["quantity"],
                        bill_id,
                    ),
                )

                conn.execute(
                    """
                    UPDATE products
                    SET
                        quantity =
                            quantity - ?,
                        updated_at =
                            datetime('now')
                    WHERE id = ?
                    """,
                    (
                        item["quantity"],
                        item["product_id"],
                    ),
                )

            # -------------------------------------------------------
            # 7. Add Khata credit
            # -------------------------------------------------------

            if payment_mode == "khata":

                _add_credit_txn(
                    conn,
                    customer_id,
                    breakup["grand_total"],
                    note=f"Bill #{bill_id}",
                )

            # -------------------------------------------------------
            # 8. Finalize bill
            # -------------------------------------------------------

            conn.execute(
                """
                UPDATE bills
                SET
                    status = 'finalized',
                    customer_id = ?,
                    payment_mode = ?,
                    payment_ref = ?,
                    subtotal = ?,
                    cgst_total = ?,
                    sgst_total = ?,
                    grand_total = ?,
                    idempotency_key = ?,
                    finalized_at =
                        datetime('now')
                WHERE id = ?
                """,
                (
                    customer_id,
                    payment_mode,
                    payment_ref,
                    breakup["subtotal"],
                    breakup["cgst_total"],
                    breakup["sgst_total"],
                    breakup["grand_total"],
                    idempotency_key,
                    bill_id,
                ),
            )

            # -------------------------------------------------------
            # 9. Build final result
            # -------------------------------------------------------

            result = _draft_bill_dict(
                conn,
                bill_id,
            )

            # Draft-only field is no longer needed.
            result.pop(
                "estimated_total",
                None,
            )

            # -------------------------------------------------------
            # 10. Save idempotency result
            # -------------------------------------------------------

            conn.execute(
                """
                INSERT INTO idempotency_keys (
                    key,
                    result_summary
                )
                VALUES (
                    ?,
                    ?
                )
                """,
                (
                    idempotency_key,
                    json.dumps(result),
                ),
            )

            return result

    finally:
        conn.close()