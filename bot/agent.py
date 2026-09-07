"""
Gemini / Google ADK agent for the Supermarket Ops Agent.

The Gemini model is responsible for understanding natural-language
requests and selecting the appropriate business tools.

Business rules remain inside the skills/database layer.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from pathlib import Path

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from bot import config
from db.connection import init_db

from skills import billing
from skills import analytics
from skills import preferences
from skills import khata

from skills.documents import (
    generate_invoice_pdf,
    generate_analysis_pptx,
)

from skills.inventory import (
    search_products,
    get_product,
    add_product,
    receive_stock,
    low_stock_report,
)


# ============================================================================
# CONTEXT
# ============================================================================

_current_message_key: ContextVar[str | None] = ContextVar(
    "current_message_key",
    default=None,
)

_current_chat_id: ContextVar[str | None] = ContextVar(
    "current_chat_id",
    default=None,
)


# ============================================================================
# BILLING TOOLS
# ============================================================================

def start_bill() -> dict:
    """Create a new draft bill."""
    return billing.start_bill()


def add_line_item(
    bill_id: int,
    product_id: int,
    quantity: float,
) -> dict:
    """Add quantity of a product to a draft bill."""

    return billing.add_line_item(
        bill_id,
        product_id,
        quantity,
    )


def set_line_item_quantity(
    bill_id: int,
    product_id: int,
    quantity: float,
) -> dict:
    """Set the absolute quantity of a product on a draft bill."""

    return billing.set_line_item_quantity(
        bill_id,
        product_id,
        quantity,
    )


def remove_line_item(
    bill_id: int,
    product_id: int,
) -> dict:
    """Remove a product completely from a draft bill."""

    return billing.remove_line_item(
        bill_id,
        product_id,
    )


def get_draft_bill(
    bill_id: int,
) -> dict:
    """Get the current draft bill and estimated total."""

    return billing.get_draft_bill(bill_id)


def finalize_bill(
    bill_id: int,
    payment_mode: str,
    payment_ref: str | None = None,
    customer_name: str | None = None,
) -> dict:
    """
    Finalize a bill.

    The idempotency key comes from Telegram message context.
    Gemini must never invent the idempotency key.
    """

    message_key = _current_message_key.get()

    if not message_key:
        raise RuntimeError(
            "Missing Telegram message key for bill finalization"
        )

    return billing.finalize_bill(
        bill_id=bill_id,
        payment_mode=payment_mode.lower().strip(),
        idempotency_key=message_key,
        payment_ref=payment_ref,
        customer_name=customer_name,
    )


# ============================================================================
# KHATA TOOLS
# ============================================================================

def get_or_create_customer(
    customer_name: str,
    phone: str | None = None,
) -> dict:
    """Get an existing Khata customer or create one."""

    return khata.get_or_create_customer(
        customer_name,
        phone,
    )


def add_credit(
    customer_name: str,
    amount: float,
    note: str | None = None,
) -> dict:
    """Add an amount owed by a customer to their Khata."""

    return khata.add_credit(
        customer_name,
        amount,
        note,
    )


def record_payment(
    customer_name: str,
    amount: float,
    note: str | None = None,
) -> dict:
    """Record a payment against an existing Khata balance."""

    return khata.record_payment(
        customer_name,
        amount,
        note,
    )


def get_khata_balance(
    customer_name: str,
) -> dict:
    """Get the outstanding Khata balance for a customer."""

    return khata.get_balance(customer_name)


# ============================================================================
# ANALYTICS TOOLS
# ============================================================================

def daily_close(
    date: str | None = None,
) -> dict:
    """Return sales, GST, payment split and top items for a day."""

    return analytics.daily_close(date)


def sales_summary(
    start_date: str,
    end_date: str,
) -> dict:
    """Return revenue, GST and bill count for a date range."""

    return analytics.sales_summary(
        start_date,
        end_date,
    )


def top_items(
    start_date: str,
    end_date: str,
    limit: int = 10,
) -> list[dict]:
    """Return top-selling products for a date range."""

    return analytics.top_items(
        start_date,
        end_date,
        limit,
    )


def gst_collected(
    start_date: str,
    end_date: str,
) -> dict:
    """Return CGST/SGST collected including GST slab breakdown."""

    return analytics.gst_collected(
        start_date,
        end_date,
    )


# ============================================================================
# PREFERENCE TOOLS
# ============================================================================

def set_preference(
    key: str,
    value: str,
) -> dict:
    """
    Save a persistent shop-owner preference.

    The owner ID comes from application configuration.
    """

    return preferences.set_preference(
        config.SHOP_OWNER_ID,
        key,
        value,
    )


def get_preference(
    key: str,
) -> str | None:
    """
    Get a persistent shop-owner preference.

    The owner ID comes from application configuration.
    """

    return preferences.get_preference(
        config.SHOP_OWNER_ID,
        key,
    )


# ============================================================================
# DOCUMENT TRACKING
# ============================================================================

_generated_files_by_chat: dict[str, list[Path]] = {}


def _register_generated_file(result: dict) -> dict:
    """
    Register a successfully generated document for Telegram delivery.
    """

    chat_id = _current_chat_id.get()

    if not chat_id:
        return result

    if not isinstance(result, dict):
        return result

    if not result.get("success"):
        return result

    path_value = result.get("path")

    if not path_value:
        return result

    path = Path(path_value)

    if not path.exists():
        return result

    _generated_files_by_chat.setdefault(
        chat_id,
        [],
    ).append(path)

    return result


def generate_invoice_pdf_tool(
    bill_id: int,
) -> dict:
    """
    Generate a PDF invoice for a finalized bill.

    The generated file is registered for Telegram delivery.
    """

    result = generate_invoice_pdf(bill_id)

    return _register_generated_file(result)


def generate_analysis_pptx_tool(
    start_date: str,
    end_date: str,
) -> dict:
    """
    Generate a PPTX sales/store analysis presentation.

    The generated file is registered for Telegram delivery.
    """

    result = generate_analysis_pptx(
        start_date,
        end_date,
    )

    return _register_generated_file(result)


def consume_generated_files(
    chat_id: str,
) -> list[Path]:
    """
    Return generated files waiting to be sent to a Telegram chat.

    Files are removed from the pending queue after being consumed.
    """

    return _generated_files_by_chat.pop(
        chat_id,
        [],
    )


# ============================================================================
# COMPLETE TOOL REGISTRY
# ============================================================================

TOOLS = [
    # ------------------------------------------------------------------------
    # Inventory — 5
    # ------------------------------------------------------------------------
    search_products,
    get_product,
    add_product,
    receive_stock,
    low_stock_report,

    # ------------------------------------------------------------------------
    # Billing — 6
    # ------------------------------------------------------------------------
    start_bill,
    add_line_item,
    set_line_item_quantity,
    remove_line_item,
    get_draft_bill,
    finalize_bill,

    # ------------------------------------------------------------------------
    # Khata — 4
    # ------------------------------------------------------------------------
    get_or_create_customer,
    add_credit,
    record_payment,
    get_khata_balance,

    # ------------------------------------------------------------------------
    # Analytics — 4
    # ------------------------------------------------------------------------
    daily_close,
    sales_summary,
    top_items,
    gst_collected,

    # ------------------------------------------------------------------------
    # Preferences — 2
    # ------------------------------------------------------------------------
    set_preference,
    get_preference,

    # ------------------------------------------------------------------------
    # Documents — 2
    # ------------------------------------------------------------------------
    generate_invoice_pdf_tool,
    generate_analysis_pptx_tool,
]


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

def _build_system_prompt() -> str:
    """
    Build the system prompt using persistent shop preferences.

    Preferences are loaded fresh from SQLite.
    """

    default_payment_mode = preferences.get_preference(
        config.SHOP_OWNER_ID,
        "default_payment_mode",
    )

    default_atta = preferences.get_preference(
        config.SHOP_OWNER_ID,
        "default_atta",
    )

    preference_lines: list[str] = []

    if default_payment_mode:
        preference_lines.append(
            f"Default payment mode: {default_payment_mode}"
        )

    if default_atta:
        preference_lines.append(
            f"Preferred atta: {default_atta}"
        )

    preferences_text = (
        "\n".join(preference_lines)
        if preference_lines
        else "No saved preferences."
    )

    return f"""
You are the AI operations agent for an Indian kirana/supermarket store.

You operate the store through natural-language conversation.

SHOP:
- Name: {config.SHOP_NAME}
- Owner ID: {config.SHOP_OWNER_ID}

PERSISTENT SHOP PREFERENCES:
{preferences_text}

CORE RULES:

1. Always use tools for product, price, GST, stock, sales,
   Khata and preference information.

2. Never invent:
   - products
   - prices
   - GST rates
   - HSN codes
   - stock quantities
   - customer balances
   - sales numbers

3. If a product name is ambiguous:
   - use search_products
   - present the matching products
   - ask the owner to clarify
   - never guess

4. BILLING WORKFLOW:
   - Start a bill using start_bill.
   - Find products using search_products.
   - Add products using add_line_item.
   - For "make it N", use set_line_item_quantity.
   - For "remove", "drop", or "delete", use remove_line_item.
   - Use get_draft_bill to review the current bill.

5. Bills are persistent database state.
   Continue editing the existing draft bill instead of creating
   a new bill for every message.

6. Never finalize a bill until the owner clearly confirms
   the bill is ready and provides a payment mode.

7. Supported payment modes:
   - cash
   - upi
   - card
   - khata

8. For UPI or card:
   - preserve a payment reference if the owner provides one.

9. For Khata:
   - customer name is required.
   - use the actual Khata tools.
   - never invent a customer balance.
   - never claim a payment succeeded if the tool rejected it.

10. Stock is decremented only during successful finalization.

11. Never bypass an insufficient-stock error.

12. Never invent an idempotency key.
    The application provides it automatically.

13. KHATA:
    - add_credit may create a new customer.
    - record_payment must never create a customer.
    - get_khata_balance must use the actual database balance.
    - Never claim a payment succeeded if the tool rejected it.

14. ANALYTICS:
    - Use analytics tools for sales, GST and top-item questions.
    - Do not calculate store totals from conversation history.

15. PREFERENCES:
    - Use set_preference when the owner asks you to remember
      a shop preference.
    - Use get_preference when a saved preference is needed.
    - Preferences belong to the shop/owner, not a Telegram chat.

16. DOCUMENTS:
    - Use generate_invoice_pdf_tool only for a finalized bill.
    - Never generate an invoice for a draft bill.
    - Use generate_analysis_pptx_tool when the owner asks for
      a sales/store analysis presentation.
    - Never claim a PDF or PPTX was generated unless the
      document tool actually succeeds.

17. INVOICE:
    - Determine the correct bill_id from the conversation
      or previous tool results.
    - Use generate_invoice_pdf_tool for the finalized bill.
    - If the bill is not finalized, do not generate the invoice.

18. ANALYSIS PRESENTATION:
    - Use generate_analysis_pptx_tool for requested sales/store analysis.
    - Use actual database analytics through the document tool.
    - Do not invent figures or insights.

19. Business rules are enforced by tools.
    Never bypass or simulate a tool result.

20. Keep responses concise and practical for a shopkeeper.

21. After a tool returns a result, use that result as the source
    of truth for your next response or tool decision.

22. When the owner asks for information requiring database state,
    call the appropriate tool before answering.

23. If a tool returns an error or rejects an operation, clearly
    explain the problem and do not pretend the operation succeeded.

24. Do not ask the owner to provide internal IDs when they can
    reasonably be obtained from previous tool results or the
    current conversation.

25. When the owner asks to add a product to a bill:
    - search for the product first unless its exact product_id
      is already known from the current conversation.
    - if multiple products match, ask the owner to clarify.

26. When the owner confirms a bill:
    - use the existing draft bill.
    - do not create another bill.
    - finalize only after payment mode is known.

27. Never modify stock directly through conversation.
    All stock changes must happen through the inventory/billing tools.
""".strip()


# ============================================================================
# ADK AGENT
# ============================================================================

def _build_agent() -> Agent:
    """Create the Gemini agent with the complete tool surface."""

    return Agent(
        name="kirana_agent",
        model="gemini-2.5-flash",
        instruction=_build_system_prompt(),
        tools=TOOLS,
    )


# ============================================================================
# PER-CHAT ADK SESSIONS
# ============================================================================

_session_service = InMemorySessionService()

_sessions: dict[str, tuple[str, str]] = {}

_sessions_lock = asyncio.Lock()


async def _get_session(
    chat_id: str,
) -> tuple[str, str]:
    """
    Get or create one ADK session for a Telegram chat.

    Database state is persistent independently of this session.
    """

    async with _sessions_lock:
        existing = _sessions.get(chat_id)

        if existing:
            return existing

        app_name = "supermarket_ops_agent"
        user_id = chat_id

        session = await _session_service.create_session(
            app_name=app_name,
            user_id=user_id,
        )

        _sessions[chat_id] = (
            app_name,
            session.id,
        )

        return (
            app_name,
            session.id,
        )


async def reset_session(
    chat_id: str,
) -> None:
    """
    Clear only the conversational ADK session.

    Database records remain untouched.
    """

    async with _sessions_lock:
        _sessions.pop(
            chat_id,
            None,
        )

    # Clear any documents that have not yet been consumed.
    _generated_files_by_chat.pop(
        chat_id,
        None,
    )


# ============================================================================
# MESSAGE HANDLING
# ============================================================================

async def handle_message(
    chat_id: str,
    text: str,
    message_key: str,
) -> str:
    """
    Send a Telegram message through Gemini/ADK.

    message_key is kept outside model-controlled arguments and is
    available to finalize_bill through ContextVar.

    chat_id is kept outside model-controlled arguments so generated
    documents can be associated with the correct Telegram chat.
    """

    message_token = _current_message_key.set(
        message_key
    )

    chat_token = _current_chat_id.set(
        chat_id
    )

    try:
        app_name, session_id = await _get_session(
            chat_id
        )

        agent = _build_agent()

        runner = Runner(
            agent=agent,
            app_name=app_name,
            session_service=_session_service,
        )

        content = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=text,
                )
            ],
        )

        final_text: str | None = None

        async for event in runner.run_async(
            user_id=chat_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:

                    texts: list[str] = []

                    for part in event.content.parts:

                        if getattr(
                            part,
                            "text",
                            None,
                        ):
                            texts.append(
                                part.text
                            )

                    if texts:
                        final_text = "\n".join(
                            texts
                        )

        if final_text:
            return final_text

        return "I couldn't produce a response."

    finally:

        _current_message_key.reset(
            message_token
        )

        _current_chat_id.reset(
            chat_token
        )


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

# Ensure the database schema exists before building the ADK agent.
init_db()


# ============================================================================
# GOOGLE ADK ENTRY POINT
# ============================================================================

root_agent = _build_agent()