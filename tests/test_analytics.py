from datetime import datetime

from db.connection import get_connection
from skills import analytics


def _create_product(
    name="Test Product",
    sell_price=105,
    gst_rate=5,
):
    conn = get_connection()

    try:
        cur = conn.execute(
            """
            INSERT INTO products
            (
                name,
                unit,
                is_loose,
                gst_rate,
                cost_price,
                sell_price,
                quantity,
                reorder_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                "piece",
                0,
                gst_rate,
                80,
                sell_price,
                10,
                2,
            ),
        )

        return cur.lastrowid

    finally:
        conn.close()


def _create_finalized_bill(
    product_id,
    quantity=2,
    payment_mode="cash",
    finalized_at="2026-09-01 12:00:00",
):
    conn = get_connection()

    try:
        # ₹105 inclusive of 5% GST:
        # taxable = ₹100
        # CGST = ₹2.50
        # SGST = ₹2.50
        line_total = 105 * quantity
        subtotal = 100 * quantity
        cgst = 2.5 * quantity
        sgst = 2.5 * quantity

        cur = conn.execute(
            """
            INSERT INTO bills
            (
                status,
                payment_mode,
                subtotal,
                cgst_total,
                sgst_total,
                grand_total,
                finalized_at
            )
            VALUES
            (
                'finalized',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                payment_mode,
                subtotal,
                cgst,
                sgst,
                line_total,
                finalized_at,
            ),
        )

        bill_id = cur.lastrowid

        conn.execute(
            """
            INSERT INTO bill_items
            (
                bill_id,
                product_id,
                quantity,
                unit_price,
                gst_rate,
                line_total
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                bill_id,
                product_id,
                quantity,
                105,
                5,
                line_total,
            ),
        )

        conn.commit()

        return bill_id

    finally:
        conn.close()


def test_sales_summary():
    product_id = _create_product()

    _create_finalized_bill(
        product_id,
        quantity=2,
        finalized_at="2026-09-01 12:00:00",
    )

    result = analytics.sales_summary(
        "2026-09-01",
        "2026-09-01",
    )

    assert result["bill_count"] == 1
    assert result["subtotal"] == 200
    assert result["cgst_total"] == 5
    assert result["sgst_total"] == 5
    assert result["gst_total"] == 10
    assert result["revenue"] == 210


def test_top_items():
    product_id = _create_product(
        name="Rice",
        sell_price=105,
        gst_rate=5,
    )

    _create_finalized_bill(
        product_id,
        quantity=3,
        finalized_at="2026-09-02 10:00:00",
    )

    result = analytics.top_items(
        "2026-09-02",
        "2026-09-02",
    )

    assert len(result) == 1
    assert result[0]["product_name"] == "Rice"
    assert result[0]["quantity"] == 3
    assert result[0]["revenue"] == 315


def test_gst_collected():
    product_id = _create_product(
        name="Milk",
        sell_price=105,
        gst_rate=5,
    )

    _create_finalized_bill(
        product_id,
        quantity=2,
        finalized_at="2026-09-03 09:00:00",
    )

    result = analytics.gst_collected(
        "2026-09-03",
        "2026-09-03",
    )

    assert result["cgst_total"] == 5
    assert result["sgst_total"] == 5
    assert result["gst_total"] == 10

    assert len(result["slabs"]) == 1
    assert result["slabs"][0]["gst_rate"] == 5
    assert result["slabs"][0]["cgst"] == 5
    assert result["slabs"][0]["sgst"] == 5


def test_daily_close():
    product_id = _create_product(
        name="Atta",
        sell_price=105,
        gst_rate=5,
    )

    _create_finalized_bill(
        product_id,
        quantity=2,
        payment_mode="upi",
        finalized_at="2026-09-04 15:00:00",
    )

    result = analytics.daily_close("2026-09-04")

    assert result["date"] == "2026-09-04"
    assert result["bill_count"] == 1
    assert result["revenue"] == 210
    assert result["gst_total"] == 10

    assert len(result["payment_modes"]) == 1
    assert result["payment_modes"][0]["payment_mode"] == "upi"
    assert result["payment_modes"][0]["amount"] == 210

    assert result["top_items"][0]["product_name"] == "Atta"