from __future__ import annotations

from datetime import date, datetime, timedelta

from db.connection import get_connection


def _validate_date(value: str, field_name: str) -> str:
    """Validate YYYY-MM-DD date format."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be in YYYY-MM-DD format"
        )

    return value


def _next_day(date_string: str) -> str:
    """Return the day after a YYYY-MM-DD date."""
    current = datetime.strptime(
        date_string,
        "%Y-%m-%d",
    ).date()

    return (current + timedelta(days=1)).isoformat()


def _today() -> str:
    return date.today().isoformat()


def daily_close(date: str | None = None) -> dict:
    """
    Return the sales summary for one day.

    Includes:
    - total revenue
    - subtotal
    - CGST
    - SGST
    - total GST
    - bill count
    - payment-mode split
    - top-selling items
    """

    target_date = date or _today()
    _validate_date(target_date, "date")

    next_date = _next_day(target_date)

    conn = get_connection()

    try:
        summary = conn.execute(
            """
            SELECT
                COUNT(*) AS bill_count,
                COALESCE(SUM(subtotal), 0) AS subtotal,
                COALESCE(SUM(cgst_total), 0) AS cgst_total,
                COALESCE(SUM(sgst_total), 0) AS sgst_total,
                COALESCE(SUM(grand_total), 0) AS revenue
            FROM bills
            WHERE status = 'finalized'
              AND finalized_at >= ?
              AND finalized_at < ?
            """,
            (
                target_date,
                next_date,
            ),
        ).fetchone()

        payment_rows = conn.execute(
            """
            SELECT
                payment_mode,
                COUNT(*) AS bill_count,
                COALESCE(SUM(grand_total), 0) AS amount
            FROM bills
            WHERE status = 'finalized'
              AND finalized_at >= ?
              AND finalized_at < ?
            GROUP BY payment_mode
            ORDER BY payment_mode
            """,
            (
                target_date,
                next_date,
            ),
        ).fetchall()

        top_rows = conn.execute(
            """
            SELECT
                p.id AS product_id,
                p.name AS product_name,
                SUM(bi.quantity) AS quantity,
                SUM(bi.line_total) AS revenue
            FROM bill_items bi
            JOIN bills b
                ON b.id = bi.bill_id
            JOIN products p
                ON p.id = bi.product_id
            WHERE b.status = 'finalized'
              AND b.finalized_at >= ?
              AND b.finalized_at < ?
            GROUP BY p.id, p.name
            ORDER BY revenue DESC
            LIMIT 10
            """,
            (
                target_date,
                next_date,
            ),
        ).fetchall()

        return {
            "date": target_date,
            "bill_count": int(summary["bill_count"]),
            "subtotal": round(float(summary["subtotal"]), 2),
            "cgst_total": round(float(summary["cgst_total"]), 2),
            "sgst_total": round(float(summary["sgst_total"]), 2),
            "gst_total": round(
                float(summary["cgst_total"])
                + float(summary["sgst_total"]),
                2,
            ),
            "revenue": round(float(summary["revenue"]), 2),
            "payment_modes": [
                {
                    "payment_mode": row["payment_mode"],
                    "bill_count": int(row["bill_count"]),
                    "amount": round(float(row["amount"]), 2),
                }
                for row in payment_rows
            ],
            "top_items": [
                {
                    "product_id": int(row["product_id"]),
                    "product_name": row["product_name"],
                    "quantity": float(row["quantity"]),
                    "revenue": round(float(row["revenue"]), 2),
                }
                for row in top_rows
            ],
        }

    finally:
        conn.close()


def sales_summary(
    start_date: str,
    end_date: str,
) -> dict:
    """
    Return revenue, GST and bill count for a date range.

    Both dates are inclusive.
    """

    _validate_date(start_date, "start_date")
    _validate_date(end_date, "end_date")

    if start_date > end_date:
        raise ValueError(
            "start_date cannot be after end_date"
        )

    end_exclusive = _next_day(end_date)

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS bill_count,
                COALESCE(SUM(subtotal), 0) AS subtotal,
                COALESCE(SUM(cgst_total), 0) AS cgst_total,
                COALESCE(SUM(sgst_total), 0) AS sgst_total,
                COALESCE(SUM(grand_total), 0) AS revenue
            FROM bills
            WHERE status = 'finalized'
              AND finalized_at >= ?
              AND finalized_at < ?
            """,
            (
                start_date,
                end_exclusive,
            ),
        ).fetchone()

        cgst = float(row["cgst_total"])
        sgst = float(row["sgst_total"])

        return {
            "start_date": start_date,
            "end_date": end_date,
            "bill_count": int(row["bill_count"]),
            "subtotal": round(float(row["subtotal"]), 2),
            "cgst_total": round(cgst, 2),
            "sgst_total": round(sgst, 2),
            "gst_total": round(cgst + sgst, 2),
            "revenue": round(float(row["revenue"]), 2),
        }

    finally:
        conn.close()


def top_items(
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> list[dict]:
    """
    Return best-selling products ranked by revenue.
    """

    _validate_date(start_date, "start_date")
    _validate_date(end_date, "end_date")

    if start_date > end_date:
        raise ValueError(
            "start_date cannot be after end_date"
        )

    if limit <= 0:
        raise ValueError("limit must be positive")

    end_exclusive = _next_day(end_date)

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                p.id AS product_id,
                p.name AS product_name,
                p.unit AS unit,
                SUM(bi.quantity) AS quantity,
                SUM(bi.line_total) AS revenue
            FROM bill_items bi
            JOIN bills b
                ON b.id = bi.bill_id
            JOIN products p
                ON p.id = bi.product_id
            WHERE b.status = 'finalized'
              AND b.finalized_at >= ?
              AND b.finalized_at < ?
            GROUP BY
                p.id,
                p.name,
                p.unit
            ORDER BY revenue DESC
            LIMIT ?
            """,
            (
                start_date,
                end_exclusive,
                limit,
            ),
        ).fetchall()

        return [
            {
                "product_id": int(row["product_id"]),
                "product_name": row["product_name"],
                "unit": row["unit"],
                "quantity": float(row["quantity"]),
                "revenue": round(float(row["revenue"]), 2),
            }
            for row in rows
        ]

    finally:
        conn.close()


def gst_collected(
    start_date: str,
    end_date: str,
) -> dict:
    """
    Return CGST and SGST collected during a date range.

    Also breaks GST down by the GST slab recorded on each bill item.
    """

    _validate_date(start_date, "start_date")
    _validate_date(end_date, "end_date")

    if start_date > end_date:
        raise ValueError(
            "start_date cannot be after end_date"
        )

    end_exclusive = _next_day(end_date)

    conn = get_connection()

    try:
        totals = conn.execute(
            """
            SELECT
                COALESCE(SUM(cgst_total), 0) AS cgst_total,
                COALESCE(SUM(sgst_total), 0) AS sgst_total
            FROM bills
            WHERE status = 'finalized'
              AND finalized_at >= ?
              AND finalized_at < ?
            """,
            (
                start_date,
                end_exclusive,
            ),
        ).fetchone()

        # GST slab is stored on bill_items as a snapshot.
        # The tax amount is reconstructed from the GST-inclusive
        # line_total:
        #
        # taxable = inclusive / (1 + rate/100)
        # GST = inclusive - taxable
        # CGST = GST / 2
        # SGST = GST / 2

        slab_rows = conn.execute(
            """
            SELECT
                bi.gst_rate,
                SUM(bi.line_total) AS gross_amount,
                SUM(
                    bi.line_total
                    - (
                        bi.line_total
                        / (1 + bi.gst_rate / 100.0)
                    )
                ) AS gst_amount
            FROM bill_items bi
            JOIN bills b
                ON b.id = bi.bill_id
            WHERE b.status = 'finalized'
              AND b.finalized_at >= ?
              AND b.finalized_at < ?
            GROUP BY bi.gst_rate
            ORDER BY bi.gst_rate
            """,
            (
                start_date,
                end_exclusive,
            ),
        ).fetchall()

        slabs = []

        for row in slab_rows:
            gst_amount = float(row["gst_amount"])

            slabs.append(
                {
                    "gst_rate": float(row["gst_rate"]),
                    "gross_amount": round(
                        float(row["gross_amount"]),
                        2,
                    ),
                    "gst_total": round(
                        gst_amount,
                        2,
                    ),
                    "cgst": round(
                        gst_amount / 2,
                        2,
                    ),
                    "sgst": round(
                        gst_amount / 2,
                        2,
                    ),
                }
            )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "cgst_total": round(
                float(totals["cgst_total"]),
                2,
            ),
            "sgst_total": round(
                float(totals["sgst_total"]),
                2,
            ),
            "gst_total": round(
                float(totals["cgst_total"])
                + float(totals["sgst_total"]),
                2,
            ),
            "slabs": slabs,
        }

    finally:
        conn.close()