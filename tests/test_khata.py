"""
Khata tests.

Covers:
- refusing payment for an unknown customer
- adding credit and reading the resulting balance
"""


import pytest

from skills import khata


def test_record_payment_refuses_for_unknown_customer():
    """
    A payment must never silently create a customer.

    This is an explicit business guardrail.
    """

    with pytest.raises(ValueError, match="No khata exists"):
        khata.record_payment(
            "Unknown Customer",
            500,
        )


def test_add_credit_then_balance_reflects_amount():
    """
    add_credit may create a first-time customer.

    Adding ₹500 should result in a ₹500 outstanding balance.
    """

    result = khata.add_credit(
        "Ramesh",
        500,
        note="Test credit",
    )

    assert result["name"] == "Ramesh"
    assert result["khata_balance"] == 500

    balance = khata.get_balance("Ramesh")

    assert balance["customer"] == "Ramesh"
    assert balance["balance"] == 500

    # Add another ₹200 and verify the cumulative balance.
    result = khata.add_credit(
        "Ramesh",
        200,
        note="Second test credit",
    )

    assert result["khata_balance"] == 700

    balance = khata.get_balance("Ramesh")

    assert balance["balance"] == 700