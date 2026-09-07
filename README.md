# Supermarket Ops Agent

A conversational AI agent that runs a small Indian kirana/supermarket end-to-end through Telegram.

The agent can receive stock, create and edit GST-correct bills, manage customer credit (Khata), check inventory and low-stock items, close the business day, remember preferences, and generate real PDF invoices and PPTX sales-analysis decks on demand.

Built with **Google ADK (Agent Development Kit)** and **Google Gemini**.

The Gemini model acts as the reasoning/orchestration layer and decides which tools to call. There is no large keyword/regex-based intent router. Business rules such as stock validation, GST calculations, oversell protection, idempotency, and Khata constraints are implemented inside the tools/skills where the actual data changes occur.

---

## Features

### 🧾 Conversational Billing

- Start a new bill through Telegram
- Add products using natural language
- Support multiple line items
- Edit quantities across multiple turns
- Remove items from a draft bill
- View the current draft bill
- Finalize bills using:
  - Cash
  - UPI
  - Card
  - Khata
- Store payment references when applicable
- Stock is deducted only when a bill is finalized

### 📦 Inventory Management

- Add new products
- Receive stock
- Check current stock
- Search products
- Track:
  - Cost price
  - Selling price
  - MRP/sell price
  - Quantity
  - Unit
  - GST rate
  - HSN code
  - Reorder level
- Low-stock detection
- Overselling is prevented at the database/tool layer
- Stock changes are recorded in a stock ledger

### 🧮 GST

- GST-inclusive selling prices
- Configurable GST rates
- HSN code support
- CGST + SGST breakup
- Per-line tax calculation and rounding
- GST totals stored with finalized bills

### 📒 Khata / Customer Credit

- Create or find customers
- Add credit transactions
- Record customer payments
- Check outstanding balance
- Prevent invalid payments/overpayments
- Khata transactions are stored in a persistent ledger

### 📊 Analytics

- Daily closing summary
- Sales summaries
- Top-selling products
- GST collected
- Payment-mode analysis
- Stock health analysis

### 📄 Documents

- Generate real PDF GST invoices
- Generate PPTX sales-analysis decks
- PPTX decks contain real charts generated from store data

### 🧠 Persistent Preferences

Store shop-owner preferences outside the model context so they persist across conversations and sessions.

### 🔐 Reliability

- SQLite transactions
- Atomic stock decrement
- Oversell protection
- Idempotency protection for repeated requests
- Concurrency tests
- Draft bills do not mutate stock until finalization

---

## Architecture

```text
                         Telegram
                            │
                            ▼
                  ┌───────────────────┐
                  │ Telegram Handler  │
                  │     (aiogram)     │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │   Google ADK      │
                  │      Agent        │
                  │                   │
                  │ Gemini reasoning  │
                  │ + tool selection  │
                  └─────────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        Inventory       Billing         Khata
          Skills         Skills         Skills
              │             │             │
              └─────────────┼─────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          Analytics      Documents     Preferences
                            │
                            ▼
                     ┌──────────────┐
                     │    SQLite    │
                     │              │
                     │ Products     │
                     │ Bills        │
                     │ Customers    │
                     │ Ledgers      │
                     │ Preferences  │
                     └──────────────┘
