# Supermarket Ops Agent

A conversational agent that runs a small Indian kirana store end-to-end from Telegram —
receiving stock, cutting GST-correct bills, running customer credit (khata), closing the
day, and generating PDF invoices / PPTX analysis decks on demand.

Built on the **Claude Agent SDK**. The model orchestrates a set of thin, well-scoped tools
(skills) — there is no keyword/regex intent router. Business rules (oversell guard, GST
maths, idempotency, khata rules) live inside the tools, at the point where data changes.

## Project layout

```
supermarket-ops-agent/
├── bot/            Telegram entrypoint + Claude Agent SDK session wiring
├── skills/         The tool surface the agent orchestrates (inventory, billing, khata,
│                   analytics, documents, preferences)
├── db/             Schema + connection/transaction helpers (SQLite/Postgres)
├── documents/      PDF invoice + PPTX analysis deck generation
├── tests/          Unit + concurrency/idempotency tests
├── scripts/        One-off utilities (e.g. seeding sample products)
├── docs/           Phase plan and architecture notes
└── assets/         Sample generated outputs, screenshots, logo, etc.
```

## Getting started

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY`
3. `python scripts/seed_products.py` to load a starter product catalogue
4. `python -m bot.main` to start polling

## Phases

See `docs/PHASES.md` for the 4-phase build plan and `docs/ARCHITECTURE.md` for the
control-loop and skill design this scaffold follows.

## Deliverables checklist (from the assignment brief)

- [ ] Live Telegram bot, handle in this README
- [ ] Built on a modern agent harness (Claude Agent SDK)
- [ ] Skills & tools (the graded core)
- [ ] PDF invoices, GST-correct
- [ ] PPTX analysis deck with real charts
- [ ] README section: harness choice, control loop, skill design, hard-parts solutions
- [ ] 4–5 min demo recording
- [ ] Private GitHub repo with collaborators invited
