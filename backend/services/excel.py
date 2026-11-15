"""Excel (.xlsx) report export via openpyxl (FR-043 / UC-25).

Sheet names and headings are in the viewer's interface language; an
Arabic workbook also opens right to left."""
import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from backend.i18n import text_direction, translate as _
from backend.services.reports import REPORT_METRICS

HEADER_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def _write_header(ws, headers):
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT


def render_portfolio_report_xlsx(summary: dict) -> bytes:
    wb = Workbook()
    rtl = text_direction() == "rtl"

    overview = wb.active
    overview.title = _("Portfolio Summary")
    _write_header(overview, [_("Metric"), _("Value")])
    for key, name in REPORT_METRICS.items():
        if key in summary and key != "open_maintenance_requests":
            overview.append([_(name), summary[key]])
    overview.column_dimensions["A"].width = 24
    overview.column_dimensions["B"].width = 18

    by_property = wb.create_sheet(_("By Property"))
    _write_header(
        by_property,
        [
            _("Property"), _("Code"), _("Total Units"), _("Occupied"), _("Occupancy %"), _("Rent Collected"),
            _("Outstanding"), _("Maintenance Cost"), _("General Expenses"), _("Total Expenses"), _("Net Income"),
            _("Open Requests"),
        ],
    )
    for p in summary.get("properties", []):
        by_property.append([
            p["property_name"], p["property_code"], p["total_units"], p["occupied_units"],
            p["occupancy_rate"], p["rent_collected"], p["rent_outstanding"], p["maintenance_cost"],
            p["general_expenses"], p["total_expenses"], p["net_income_estimate"],
            p["open_maintenance_requests"],
        ])
    for col, width in zip("ABCDEFGHIJKL", (24, 12, 10, 10, 12, 14, 12, 16, 16, 14, 14, 14)):
        by_property.column_dimensions[col].width = width

    for ws in (overview, by_property):
        ws.sheet_view.rightToLeft = rtl

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def render_maintenance_summary_xlsx(summary: dict) -> bytes:
    """FR-036 maintenance summary as a workbook: the period, then open, in
    progress and closed requests per property, with a total row when the
    summary covers more than one property."""
    wb = Workbook()
    ws = wb.active
    ws.title = _("Maintenance Summary")
    ws.append([_("From"), summary["start"].isoformat()])
    ws.append([_("To"), summary["end"].isoformat()])
    ws.append([])
    _write_header(ws, [_("Property"), _("Open"), _("In Progress"), _("Closed"), _("Total")])
    for row in summary["properties"]:
        ws.append([row["property_name"], row["open"], row["in_progress"], row["closed"], row["total"]])
    if len(summary["properties"]) > 1:
        totals = summary["totals"]
        ws.append([_("All properties"), totals["open"], totals["in_progress"], totals["closed"], totals["total"]])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
    for col, width in zip("ABCDE", (28, 12, 14, 12, 12)):
        ws.column_dimensions[col].width = width
    ws.sheet_view.rightToLeft = text_direction() == "rtl"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
