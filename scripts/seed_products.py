"""
Seeds the DB with the sample SKUs named in the assignment brief so the bot has real
grounding data to demo against.

Run: python scripts/seed_products.py
"""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent)
)

from db.connection import get_connection, init_db


SAMPLE_PRODUCTS = [

    (
        "Aashirvaad Atta 5kg",
        "packet",
        0,
        "1101",
        5,
        210,
        245,
        40,
        10,
    ),

    (
        "Tata Salt 1kg",
        "packet",
        0,
        "2501",
        5,
        18,
        24,
        60,
        15,
    ),

    (
        "Amul Butter 100g",
        "packet",
        0,
        "0405",
        12,
        48,
        62,
        30,
        10,
    ),

    (
        "Fortune Sunflower Oil 1L",
        "packet",
        0,
        "1512",
        5,
        130,
        155,
        25,
        8,
    ),

    (
        "Maggi 70g",
        "packet",
        0,
        "1902",
        12,
        10,
        14,
        100,
        20,
    ),

    (
        "Parle-G",
        "packet",
        0,
        "1905",
        18,
        8,
        10,
        100,
        20,
    ),

    (
        "Surf Excel 1kg",
        "packet",
        0,
        "3402",
        18,
        90,
        115,
        20,
        5,
    ),

    (
        "Sugar (loose)",
        "kg",
        1,
        "1701",
        0,
        38,
        45,
        50,
        10,
    ),

    (
        "Rice (loose)",
        "kg",
        1,
        "1006",
        0,
        32,
        40,
        80,
        15,
    ),

    (
        "Toor Dal (loose)",
        "kg",
        1,
        "0713",
        0,
        95,
        115,
        30,
        8,
    ),
]


def seed() -> None:

    init_db()

    conn = get_connection()

    conn.executemany(
        """INSERT INTO products
           (name, unit, is_loose, hsn_code, gst_rate,
            cost_price, sell_price, quantity, reorder_level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        SAMPLE_PRODUCTS,
    )

    conn.close()

    print(
        f"Seeded {len(SAMPLE_PRODUCTS)} products."
    )


if __name__ == "__main__":
    seed()