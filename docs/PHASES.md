# Build phases

Four phases across the 5-day window. Each phase ends in something demoable.

## Phase 1 — Foundations (schema, bot skeleton, control loop)

- Design and create the DB schema (`db/schema.sql`): products, stock_ledger, bills,
  bill_items, customers, khata_ledger, preferences, idempotency_keys.
- Stand up the Telegram bot (`bot/telegram_handler.py`) and wire it to a Claude Agent SDK
  session (`bot/agent.py`).
- Register one trivial tool (e.g. `get_product`) end-to-end to prove the full loop:
  Telegram message → agent reasons → tool call → DB read → reply.
- Exit criteria: messaging the bot "how much sugar is left?" returns a real DB-backed answer.

## Phase 2 — Core commerce (inventory + billing)

- `skills/inventory.py`: `add_product`, `receive_stock`, `search_products`,
  `low_stock_report`.
- `skills/billing.py`: `start_bill`, `add_line_item`, `remove_line_item`,
  `get_draft_bill`, `finalize_bill`.
- GST engine: per-item HSN/slab lookup, CGST/SGST split, rounding, tax breakup.
- Oversell guard and stock decrement enforced inside `finalize_bill`'s DB transaction.
- Idempotency: `finalize_bill` takes the Telegram `update_id` as an idempotency key so a
  retried webhook can't double-bill or double-decrement stock.
- Exit criteria: a multi-turn bill (add items across messages, edit mid-build, finalize)
  works, and refuses to oversell.

## Phase 3 — Credit, close & memory

- `skills/khata.py`: `get_or_create_customer`, `add_credit`, `record_payment`,
  `get_balance`. Refuses to settle a customer that doesn't exist.
- `skills/analytics.py`: `daily_close`, `sales_summary`, `top_items`, `gst_collected`.
- `skills/preferences.py`: `get_preference`, `set_preference` — default payment mode,
  preferred brand, shop name/GSTIN — stored independent of any single chat thread.
- Exit criteria: set a preference, start a `/new` chat, confirm it's still applied.

## Phase 4 — Artifacts, hardening & submission

- `documents/invoice_template.py`: GST-correct PDF invoice generated from a finalized bill.
- `documents/deck_template.py`: PPTX analysis deck with real charts (sales trend, top
  items, stock health, GST collected).
- Concurrency test: a sale and a stock-in in flight at once must not corrupt stock
  (`tests/test_concurrency.py`).
- Write up the harness choice, control loop, skill design and hard-parts solutions in the
  README. Record the 4–5 min demo. Deploy, keep the bot running, invite collaborators.

## Hard-parts → where they're solved

| Hard part | Lives in |
|---|---|
| Grounding (no invented prices/stock) | All skills read from `db/`, never from the prompt |
| Oversell guard | `skills/billing.py::finalize_bill` transaction |
| GST correctness | `skills/billing.py` GST engine + `db/schema.sql` product tax fields |
| Multi-turn bills | `skills/billing.py` draft-bill state in DB, not conversation memory |
| Idempotency | `db/schema.sql::idempotency_keys` + `finalize_bill` |
| Concurrency | `db/connection.py` transaction helpers (`BEGIN IMMEDIATE` / `SELECT ... FOR UPDATE`) |
| Guardrails (no sub-cost sale, no khata on unknown customer) | Respective skill functions |
| Real artifacts | `documents/` |
| Memory across sessions | `skills/preferences.py` + `db/schema.sql::preferences` (outside the chat context) |
