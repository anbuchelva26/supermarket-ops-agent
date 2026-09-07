-- Supermarket Ops Agent — core schema
-- Works on SQLite as-is; for Postgres swap AUTOINCREMENT -> SERIAL/IDENTITY.

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                 -- e.g. "Aashirvaad Atta 5kg"
    unit            TEXT NOT NULL,                  -- kg | g | l | ml | packet | dozen | piece
    is_loose        INTEGER NOT NULL DEFAULT 0,     -- 1 = sold loose (e.g. rice by the kg)
    hsn_code        TEXT,
    gst_rate        REAL NOT NULL DEFAULT 0,        -- e.g. 0, 5, 12, 18
    cost_price      REAL NOT NULL,
    sell_price      REAL NOT NULL,                  -- MRP or sell price
    quantity        REAL NOT NULL DEFAULT 0,
    reorder_level   REAL NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stock_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    change_qty      REAL NOT NULL,                  -- positive = stock-in, negative = sale
    reason          TEXT NOT NULL,                   -- 'receive' | 'sale' | 'adjustment'
    reference_id    INTEGER,                         -- bill id, if reason = 'sale'
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    phone           TEXT,
    khata_balance   REAL NOT NULL DEFAULT 0,        -- amount customer owes the shop
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS khata_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    amount          REAL NOT NULL,                  -- positive = credit added, negative = payment
    note            TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    status          TEXT NOT NULL DEFAULT 'draft',  -- 'draft' | 'finalized' | 'void'
    customer_id     INTEGER REFERENCES customers(id),
    payment_mode    TEXT,                            -- 'cash' | 'upi' | 'card' | 'khata'
    payment_ref     TEXT,
    subtotal        REAL,
    cgst_total      REAL,
    sgst_total      REAL,
    grand_total     REAL,
    idempotency_key TEXT UNIQUE,                     -- Telegram update_id on finalize
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    finalized_at    TEXT
);

CREATE TABLE IF NOT EXISTS bill_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id         INTEGER NOT NULL REFERENCES bills(id),
    product_id      INTEGER NOT NULL REFERENCES products(id),
    quantity        REAL NOT NULL,
    unit_price      REAL NOT NULL,                  -- snapshot at time of adding
    gst_rate        REAL NOT NULL,                   -- snapshot at time of adding
    line_total      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id        TEXT NOT NULL,                  -- shop/owner identifier, not chat id
    key             TEXT NOT NULL,                   -- 'default_payment_mode' | 'default_atta' | ...
    value            TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(owner_id, key)
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key             TEXT PRIMARY KEY,               -- Telegram update_id
    handled_at      TEXT NOT NULL DEFAULT (datetime('now')),
    result_summary  TEXT
);

CREATE INDEX IF NOT EXISTS idx_stock_ledger_product ON stock_ledger(product_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);
CREATE INDEX IF NOT EXISTS idx_khata_ledger_customer ON khata_ledger(customer_id);
