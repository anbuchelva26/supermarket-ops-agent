# Architecture

## Control loop

Telegram message → `bot/agent.py` starts/continues a Claude Agent SDK session for that
chat → the model reasons over the message and the tool schemas in `skills/` → calls one or
more tools, chaining as needed within a turn → each tool result is fed back to the model →
the model either calls another tool or replies in plain language.

No regex/keyword router. The model decides which skill to call based on tool descriptions,
including asking a clarifying question (as a normal model turn, not a hardcoded branch)
when a request is ambiguous — e.g. "add atta" with two matching products.

## Persistence vs. conversation memory

Two different lifetimes, intentionally kept apart:

- **Conversation memory** (Claude Agent SDK session) — scoped to one Telegram chat thread.
  Cleared on `/new`.
- **Persistent store** (`db/`) — SQLite (or Postgres), survives restarts and `/new` chats.
  Stock, bills, khata balances, and **owner preferences** all live here. Preferences are
  looked up by shop/owner ID, not by chat thread, which is how they survive a `/new` chat.

## Why this harness

Claude Agent SDK gives an out-of-the-box observe → reason → act → feed-back loop and native
tool-calling, which matches the brief's requirement directly (no bespoke state machine, no
LangGraph-style node-per-command graph).

## Skill surface

Each skill module in `skills/` exposes a small number of narrow tools (not one giant
"do_everything" tool). Thin tools compose better — the model can chain
`search_products → add_line_item → add_line_item → finalize_bill` in one turn instead of
needing a single tool that guesses the whole bill from one string.
