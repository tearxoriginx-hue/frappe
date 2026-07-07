import io
import os
import re

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

import frappe
from frappe.utils import scrub_urls
from frappe.utils.pdf import (
    cleanup,
    get_wkhtmltopdf_version,
    inline_private_images,
    prepare_options,
    read_options_from_html,
)

PDF_CONTENT_ERRORS = [
    "ContentNotFoundError",
    "ContentOperationNotPermittedError",
    "UnknownContentError",
    "RemoteHostClosedError",
]


def get_pdf(html, options=None, output=None):
    html = scrub_urls(html)
    html, wk_options = prepare_options(html, options)

    pw_options = _convert_to_playwright_options(wk_options)
    html = _prepare_html(html)

    try:
        pdf_bytes = _generate_pdf(html, pw_options)
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        if any(err in str(e) for err in PDF_CONTENT_ERRORS):
            frappe.throw(frappe._("PDF generation failed because of broken content"))
        raise
    finally:
        cleanup(wk_options)

    if "password" in wk_options:
        password = wk_options["password"]

    if output:
        output.append_pages_from_reader(reader)
        return output

    writer = PdfWriter()
    writer.append_pages_from_reader(reader)

    if "password" in wk_options:
        writer.encrypt(password)

    return _get_file_data_from_writer(writer)


def _convert_to_playwright_options(wk_options):
    result = {
        "print_background": True,
        "margin": {"top": "15mm", "right": "15mm", "bottom": "15mm", "left": "15mm"},
    }

    page_size = wk_options.get("page-size") or "A4"
    if page_size == "Custom":
        if wk_options.get("page-width") and wk_options.get("page-height"):
            result["width"] = wk_options["page-width"]
            result["height"] = wk_options["page-height"]
    else:
        result["format"] = page_size

    for side in ("top", "bottom", "left", "right"):
        key = f"margin-{side}"
        if key in wk_options:
            result["margin"][side] = wk_options[key]

    header_html = wk_options.get("header-html")
    footer_html = wk_options.get("footer-html")
    if header_html or footer_html:
        result["display_header_footer"] = True
        result["header_template"] = _read_html_file(header_html) if header_html else "<span></span>"
        result["footer_template"] = _read_html_file(footer_html) if footer_html else "<span></span>"

    header_spacing = wk_options.get("header-spacing")
    if header_spacing:
        result["margin"]["top"] = f"{header_spacing}mm"

    orientation = wk_options.get("orientation")
    if orientation:
        result["landscape"] = orientation == "Landscape"

    return result


def _read_html_file(path):
    if path and os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return "<span></span>"


def _prepare_html(html):
    html = inline_private_images(html)
    html = re.sub(r"<!-- pdf_footer_html.*?pdf_footer_html -->", "", html, flags=re.DOTALL)
    html = re.sub(r"<!-- pdf_header_html.*?pdf_header_html -->", "", html, flags=re.DOTALL)
    return html


def _generate_pdf(html, pw_options):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf_bytes = page.pdf(**pw_options)
        browser.close()
        return pdf_bytes


def _get_file_data_from_writer(writer_obj):
    stream = io.BytesIO()
    writer_obj.write(stream)
    stream.seek(0)
    return stream.read()
