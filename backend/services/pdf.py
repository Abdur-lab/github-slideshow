"""Server-side PDF generation using reportlab (pure-Python, no native
system libraries required — a deliberate swap for WeasyPrint so Docker
builds stay simple).

PDFs are written in the viewer's interface language. ReportLab draws text
exactly as given, so Arabic needs two extra steps: arabic_reshaper joins the
letters into their connected forms, and python-bidi puts each line into
right-to-left display order. Arabic PDFs use the bundled DejaVu Sans font,
which has both the Arabic letter forms and Latin (names, codes, emails)."""
import io
import os
import re
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.i18n import current_language, label, render_message, text_direction
from backend.services.reports import REPORT_METRICS

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
ARABIC_LETTER = re.compile("[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
ISOLATES = re.compile("[\u2066-\u2069]")
MIRRORED = str.maketrans("()[]{}<>«»", ")(][}{><»«")
MARGIN = 0.75 * inch


def _register_fonts() -> None:
    if "DejaVuSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))


class _Writer:
    """Builds translated paragraphs and tables for the current language."""

    def __init__(self):
        self.rtl = text_direction() == "rtl"
        self.width = letter[0] - 2 * MARGIN
        base = getSampleStyleSheet()
        if not self.rtl:
            self.styles = {name: base[name] for name in ("Title", "Normal", "Heading3")}
            self.font, self.bold = "Helvetica", "Helvetica-Bold"
            return
        _register_fonts()
        self.font, self.bold = "DejaVuSans", "DejaVuSans-Bold"
        self.styles = {
            name: ParagraphStyle(
                f"{name}-rtl", parent=base[name], fontName=self.bold if name != "Normal" else self.font,
                alignment=TA_RIGHT if name != "Title" else base[name].alignment,
            )
            for name in ("Title", "Normal", "Heading3")
        }

    def t(self, text: str, **values) -> str:
        """Translate a message. On right-to-left pages, values without Arabic
        (dates, codes, amounts, Latin names) are isolated so they keep their order."""
        if self.rtl:
            values = {
                key: value if ARABIC_LETTER.search(str(value)) else f"\u2066{value}\u2069"
                for key, value in values.items()
            }
        return render_message(text, **values)

    @staticmethod
    def _mirror_brackets(text: str) -> str:
        """python-bidi reorders right-to-left text but does not mirror brackets, so a
        "(" in the Arabic part would be drawn facing the wrong way. Swap them here,
        leaving brackets inside isolated left-to-right values alone."""
        out, depth = [], 0
        for ch in text:
            if ch in "\u2066\u2067\u2068":
                depth += 1
            elif ch == "\u2069":
                depth = max(depth - 1, 0)
            out.append(ch.translate(MIRRORED) if depth == 0 else ch)
        return "".join(out)

    @staticmethod
    def _visual(text: str) -> str:
        return ISOLATES.sub("", get_display(arabic_reshaper.reshape(_Writer._mirror_brackets(text)), base_dir="R"))

    def para(self, text: str, style: str = "Normal") -> Paragraph:
        st = self.styles[style]
        if not self.rtl:
            return Paragraph(escape(text), st)
        # Wrap in reading order first, then reorder each line, so a long
        # paragraph still reads from its first line to its last.
        lines = simpleSplit(arabic_reshaper.reshape(self._mirror_brackets(text)), st.fontName, st.fontSize, self.width)
        visual = [ISOLATES.sub("", get_display(line, base_dir="R")) for line in lines]
        return Paragraph("<br/>".join(escape(line) for line in visual), st)

    def cell(self, value) -> str:
        text = "" if value is None else str(value)
        # A date, code, amount or Latin name is already in display order.
        return self._visual(text) if self.rtl and ARABIC_LETTER.search(text) else text

    def table(self, rows, col_widths, style_commands, header_row: bool = True) -> Table:
        rows = [[self.cell(value) for value in row] for row in rows]
        commands = list(style_commands) + [("FONTNAME", (0, 0), (-1, -1), self.font)]
        if header_row:
            commands.append(("FONTNAME", (0, 0), (-1, 0), self.bold))
        if self.rtl:
            # Mirror the columns so the first column sits on the right.
            rows = [list(reversed(row)) for row in rows]
            col_widths = list(reversed(col_widths))
            commands = [_mirror(cmd, len(col_widths)) for cmd in commands] + [("ALIGN", (0, 0), (-1, -1), "RIGHT")]
        table = Table(rows, colWidths=col_widths)
        table.setStyle(TableStyle(commands))
        return table


def _mirror(command, ncols: int):
    """Flip a TableStyle command's column range for a mirrored table."""
    name, (c0, r0), (c1, r1), *rest = command
    c0, c1 = c0 % ncols, c1 % ncols
    return (name, (ncols - 1 - c1, r0), (ncols - 1 - c0, r1), *rest)


def _build(elements) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=MARGIN, bottomMargin=MARGIN, leftMargin=MARGIN, rightMargin=MARGIN,
        lang=current_language(),
    )
    doc.build(elements)
    return buffer.getvalue()


def render_rent_statement_pdf(
    lease, payments, generated_by: str, charges=None, period_start=None, period_end=None, period_totals=None
) -> bytes:
    w = _Writer()
    t = w.t
    elements = [
        w.para(t("RentalPro — Rent Statement"), "Title"),
        w.para(t("Tenant: {name}", name=lease.tenant.user.full_name)),
        # One value, so the brackets stay with it on right-to-left pages.
        w.para(t("Unit: {unit}", unit=f"{lease.unit.unit_code} ({lease.unit.property.name})")),
        w.para(t("Lease term: {start} to {end}", start=lease.start_date, end=lease.end_date)),
    ]
    if period_start:
        elements.append(w.para(t("Statement period: {start} to {end}", start=period_start, end=period_end)))
    elements.append(w.para(t("Generated by {name}", name=generated_by)))
    elements.append(Spacer(1, 0.3 * inch))

    if period_totals:
        elements.append(w.para(t("Opening balance: {amount}", amount=f"{period_totals['opening_balance']:.2f}")))

    rows = [[t("Date"), t("Type"), t("Description"), t("Amount"), t("Receipt #")]]
    for p in payments:
        rows.append([str(p.paid_at.date()), t("Payment"), p.notes or t("Rent payment"), f"-{p.amount:.2f}", p.receipt_number])
    for c in charges or []:
        rows.append([str(c.charged_at), label(c.charge_type), c.description, f"{c.amount:.2f}", "-"])
    elements.append(
        w.table(
            rows,
            [1.1 * inch, 1.0 * inch, 2.1 * inch, 1.0 * inch, 1.8 * inch],
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ],
        )
    )
    elements.append(Spacer(1, 0.3 * inch))

    if period_totals:
        elements.append(w.para(t("Rent charged this period: {amount}", amount=f"{period_totals['rent_in_period']:.2f}")))
        if period_totals["charges_in_period"]:
            elements.append(
                w.para(t("Operational/sundry charges this period: {amount}", amount=f"{period_totals['charges_in_period']:.2f}"))
            )
        elements.append(w.para(t("Paid this period: {amount}", amount=f"{period_totals['payments_in_period']:.2f}")))
        elements.append(w.para(t("Closing balance: {amount}", amount=f"{period_totals['closing_balance']:.2f}"), "Heading3"))
    else:
        elements.append(w.para(t("Rent charged to date: {amount}", amount=f"{lease.total_due_to_date():.2f}")))
        if lease.current_monthly_rent != lease.monthly_rent:
            elements.append(
                w.para(
                    t(
                        "Current monthly rent: {current} (original {original}).",
                        current=f"{lease.current_monthly_rent:.2f}", original=f"{lease.monthly_rent:.2f}",
                    )
                )
            )
        if charges:
            elements.append(w.para(t("Operational/sundry charges: {amount}", amount=f"{lease.total_charges:.2f}")))
        elements.append(w.para(t("Total paid: {amount}", amount=f"{lease.total_paid:.2f}")))
        elements.append(w.para(t("Outstanding balance: {amount}", amount=f"{lease.balance:.2f}"), "Heading3"))

    return _build(elements)


def render_payment_receipt_pdf(payment, lease, balance_after: float, generated_by: str = None) -> bytes:
    w = _Writer()
    t = w.t
    elements = [
        w.para(t("RentalPro — Payment Receipt"), "Title"),
        w.para(t("Receipt #: {receipt}", receipt=payment.receipt_number)),
        Spacer(1, 0.2 * inch),
    ]

    rows = [
        [t("Tenant"), lease.tenant.user.full_name],
        [t("Unit"), f"{lease.unit.unit_code} ({lease.unit.property.name})"],
        [t("Date Paid"), str(payment.paid_at.date())],
        [t("Amount Paid"), f"{payment.amount:.2f}"],
        [t("Method"), label(payment.method)],
        [t("Notes"), payment.notes or "-"],
    ]
    elements.append(
        w.table(
            rows,
            [1.5 * inch, 4.5 * inch],
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ],
            header_row=False,
        )
    )
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(w.para(t("Balance after this payment: {amount}", amount=f"{balance_after:.2f}"), "Heading3"))
    if generated_by:
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(w.para(t("Recorded by {name}", name=generated_by)))

    return _build(elements)


def _metric_value(key, value) -> str:
    if key == "occupancy_rate":
        return f"{value}%"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def render_property_report_pdf(property_obj, summary: dict) -> bytes:
    """property_obj=None reports on the whole portfolio."""
    w = _Writer()
    t = w.t
    if property_obj is None:
        heading = t("All Properties (Portfolio)")
    else:
        heading = t("Property: {name}", name=f"{property_obj.name} ({property_obj.property_code})")
    elements = [w.para(t("RentalPro — Property Performance Report"), "Title"), w.para(heading), Spacer(1, 0.3 * inch)]
    rows = [[t("Metric"), t("Value")]] + [
        [t(name), _metric_value(key, summary[key])] for key, name in REPORT_METRICS.items() if key in summary
    ]
    elements.append(
        w.table(
            rows,
            [3 * inch, 2 * inch],
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ],
        )
    )
    return _build(elements)
