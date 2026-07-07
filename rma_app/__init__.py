__version__ = "0.0.1"

try:
    from rma_app.utils.pdf import get_pdf
    import frappe.utils.pdf
    frappe.utils.pdf.get_pdf = get_pdf
except ImportError:
    # PDF generation features not available
    pass
