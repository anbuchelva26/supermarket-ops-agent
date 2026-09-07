"""
Renders a finalized bill as a GST-correct PDF invoice: line items, per-item HSN + GST
rate, CGST/SGST breakup, grand total, shop name/GSTIN from preferences (stretch:
branded/templated invoices).
"""


def render_invoice(bill: dict, shop_details: dict) -> str:
    """Returns the output PDF file path. Implement with reportlab/weasyprint."""
    raise NotImplementedError
