import pytest

from skills import inventory


def test_add_product_starts_at_zero_stock():
    product = inventory.add_product(
        "Test Salt 1kg", "packet", gst_rate=5, cost_price=18, sell_price=24,
        hsn_code="2501", reorder_level=5,
    )
    assert product["quantity"] == 0
    assert product["name"] == "Test Salt 1kg"


def test_receive_stock_increments_quantity_and_ledger():
    product = inventory.add_product(
        "Test Maggi 70g", "packet", gst_rate=12, cost_price=10, sell_price=14, reorder_level=10,
    )
    updated = inventory.receive_stock(product["id"], 50, cost_price=11)
    assert updated["quantity"] == 50
    assert updated["cost_price"] == 11

    again = inventory.receive_stock(product["id"], 25)
    assert again["quantity"] == 75


def test_receive_stock_rejects_non_positive_quantity():
    product = inventory.add_product(
        "Test Rice (loose)", "kg", gst_rate=0, cost_price=32, sell_price=40, is_loose=True,
    )
    with pytest.raises(ValueError):
        inventory.receive_stock(product["id"], 0)
    with pytest.raises(ValueError):
        inventory.receive_stock(product["id"], -5)


def test_receive_stock_rejects_unknown_product():
    with pytest.raises(ValueError):
        inventory.receive_stock(99999, 10)


def test_low_stock_report_returns_only_items_at_or_below_reorder_level():
    low = inventory.add_product("Low Item", "kg", gst_rate=0, cost_price=10, sell_price=12, reorder_level=20)
    inventory.receive_stock(low["id"], 5)

    high = inventory.add_product("High Item", "kg", gst_rate=0, cost_price=10, sell_price=12, reorder_level=5)
    inventory.receive_stock(high["id"], 50)

    report = inventory.low_stock_report()
    names = {p["name"] for p in report}
    assert "Low Item" in names
    assert "High Item" not in names


def test_search_products_partial_case_insensitive_match():
    inventory.add_product("Aashirvaad Atta 5kg", "packet", gst_rate=5, cost_price=210, sell_price=245)
    inventory.add_product("Tata Salt 1kg", "packet", gst_rate=5, cost_price=18, sell_price=24)

    results = inventory.search_products("atta")
    names = {p["name"] for p in results}
    assert "Aashirvaad Atta 5kg" in names
    assert "Tata Salt 1kg" not in names


def test_get_product_raises_for_unknown_id():
    with pytest.raises(ValueError):
        inventory.get_product(99999)
