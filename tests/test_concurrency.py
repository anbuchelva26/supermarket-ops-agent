"""
Concurrency test.

A sale and a stock receipt are executed concurrently for the
same product.

SQLite BEGIN IMMEDIATE in db.connection.transaction() should
serialize the two write transactions so there is no lost update.
"""

from concurrent.futures import ThreadPoolExecutor

from skills import billing, inventory


def test_concurrent_sale_and_restock_do_not_corrupt_stock():
    """
    Starting stock = 10
    Sale          = 3
    Restock       = 5

    Expected final stock = 10 - 3 + 5 = 12
    """

    product = inventory.add_product(
        "Concurrent Test Item",
        "packet",
        gst_rate=5,
        cost_price=40,
        sell_price=50,
    )

    inventory.receive_stock(
        product["id"],
        10,
    )

    bill = billing.start_bill()

    billing.add_line_item(
        bill["id"],
        product["id"],
        3,
    )

    def finalize_sale():
        return billing.finalize_bill(
            bill_id=bill["id"],
            payment_mode="cash",
            idempotency_key="concurrency-test-sale",
        )

    def receive_stock():
        return inventory.receive_stock(
            product["id"],
            5,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(finalize_sale),
            executor.submit(receive_stock),
        ]

        # Calling result() propagates any exception from either thread.
        for future in futures:
            future.result()

    final_product = inventory.get_product(product["id"])

    assert final_product["quantity"] == 12