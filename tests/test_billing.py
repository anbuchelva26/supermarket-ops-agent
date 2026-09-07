"""
Billing tests.

Covers:
- GST breakup correctness
- oversell protection
- finalize idempotency
"""

import pytest

from skills import billing, inventory


def make_product(
    name="Test Sugar 1kg",
    gst_rate=5,
    cost_price=40,
    sell_price=50,
    quantity=10,
):
    product = inventory.add_product(
        name,
        "packet",
        gst_rate=gst_rate,
        cost_price=cost_price,
        sell_price=sell_price,
    )
    inventory.receive_stock(product["id"], quantity)
    return product


def make_bill(product_id, quantity):
    bill = billing.start_bill()
    billing.add_line_item(
        bill["id"],
        product_id,
        quantity,
    )
    return bill["id"]


def test_gst_breakup_splits_cgst_sgst_evenly():
    """
    For a GST-inclusive ₹105 item at 5% GST:

        taxable value = ₹100
        total GST      = ₹5
        CGST           = ₹2.50
        SGST           = ₹2.50
        grand total    = ₹105
    """

    product = make_product(
        name="GST Test Item",
        gst_rate=5,
        cost_price=80,
        sell_price=105,
        quantity=5,
    )

    bill_id = make_bill(product["id"], 1)

    result = billing.finalize_bill(
        bill_id=bill_id,
        payment_mode="cash",
        idempotency_key="gst-test-001",
    )

    assert result["subtotal"] == 100.00
    assert result["cgst_total"] == 2.50
    assert result["sgst_total"] == 2.50
    assert result["grand_total"] == 105.00


def test_finalize_bill_refuses_when_stock_insufficient():
    """
    The bill must be rejected when requested quantity exceeds live stock.

    Nothing should be finalized and stock must remain unchanged.
    """

    product = make_product(
        name="Limited Sugar",
        gst_rate=5,
        cost_price=40,
        sell_price=50,
        quantity=3,
    )

    bill_id = make_bill(product["id"], 10)

    with pytest.raises(ValueError, match="Not enough"):
        billing.finalize_bill(
            bill_id=bill_id,
            payment_mode="cash",
            idempotency_key="oversell-test-001",
        )

    current = inventory.get_product(product["id"])

    assert current["quantity"] == 3

    draft = billing.get_draft_bill(bill_id)

    assert draft["status"] == "draft"


def test_finalize_bill_is_idempotent_on_retry():
    """
    Calling finalize_bill twice with the same idempotency key must
    return the same result and decrement stock only once.
    """

    product = make_product(
        name="Idempotency Sugar",
        gst_rate=5,
        cost_price=40,
        sell_price=50,
        quantity=10,
    )

    bill_id = make_bill(product["id"], 2)

    first = billing.finalize_bill(
        bill_id=bill_id,
        payment_mode="upi",
        idempotency_key="telegram-update-123",
        payment_ref="UPI-REF-123",
    )

    stock_after_first = inventory.get_product(product["id"])

    assert stock_after_first["quantity"] == 8

    second = billing.finalize_bill(
        bill_id=bill_id,
        payment_mode="upi",
        idempotency_key="telegram-update-123",
        payment_ref="UPI-REF-123",
    )

    stock_after_second = inventory.get_product(product["id"])

    assert stock_after_second["quantity"] == 8
    assert second == first
def test_finalize_bill_with_khata_creates_customer_and_adds_balance():
    """
    A Khata bill should:
    - finalize successfully
    - decrement stock
    - create the customer if needed
    - add the full GST-inclusive bill total to Khata
    """

    product = make_product(
        name="Khata Rice",
        gst_rate=5,
        cost_price=80,
        sell_price=105,
        quantity=10,
    )

    bill_id = make_bill(product["id"], 2)

    result = billing.finalize_bill(
        bill_id=bill_id,
        payment_mode="khata",
        idempotency_key="khata-bill-001",
        customer_name="Ravi",
    )

    assert result["status"] == "finalized"
    assert result["payment_mode"] == "khata"
    assert result["grand_total"] == 210.00

    current = inventory.get_product(product["id"])

    assert current["quantity"] == 8

    from skills import khata

    balance = khata.get_balance("Ravi")

    assert balance["customer"] == "Ravi"
    assert balance["balance"] == 210.00


def test_khata_bill_is_idempotent_and_does_not_double_credit():
    """
    Retrying the same Khata finalization with the same idempotency key
    must not:
    - decrement stock again
    - increase Khata balance again
    """

    product = make_product(
        name="Khata Sugar",
        gst_rate=5,
        cost_price=40,
        sell_price=105,
        quantity=10,
    )

    bill_id = make_bill(product["id"], 1)

    first = billing.finalize_bill(
        bill_id=bill_id,
        payment_mode="khata",
        idempotency_key="khata-retry-001",
        customer_name="Arun",
    )

    stock_after_first = inventory.get_product(product["id"])

    assert stock_after_first["quantity"] == 9

    from skills import khata

    balance_after_first = khata.get_balance("Arun")

    assert balance_after_first["balance"] == 105.00

    second = billing.finalize_bill(
        bill_id=bill_id,
        payment_mode="khata",
        idempotency_key="khata-retry-001",
        customer_name="Arun",
    )

    stock_after_second = inventory.get_product(product["id"])
    balance_after_second = khata.get_balance("Arun")

    assert stock_after_second["quantity"] == 9
    assert balance_after_second["balance"] == 105.00
    assert second == first