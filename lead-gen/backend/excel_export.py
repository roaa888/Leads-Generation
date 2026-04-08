"""
Builds a formatted .xlsx file from leads data.
Color palette matches the frontend UI.
"""

import io
from openpyxl import Workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, GradientFill
)
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.utils import get_column_letter

# ── Brand palette ────────────────────────────────────────────────────────────
C_DARK    = "055B65"   # headers / accents
C_GREEN   = "1BD488"   # Verified
C_MID     = "45828B"   # Partial / chart accent
C_LIGHT   = "B2C9C5"   # Missing Email / subtle bg
C_WHITE   = "FFFFFF"
C_ROW_ALT = "F0F6F6"   # alternating row tint
C_BORDER  = "D0E4E6"

# ── Status colours ────────────────────────────────────────────────────────────
STATUS_FILL = {
    "Verified":      PatternFill("solid", fgColor=C_GREEN),
    "New":           PatternFill("solid", fgColor=C_MID),
    "Missing Email": PatternFill("solid", fgColor=C_LIGHT),
}
STATUS_FONT = {
    "Verified":      Font(color=C_WHITE, bold=True, size=9),
    "New":           Font(color=C_WHITE, bold=True, size=9),
    "Missing Email": Font(color="555555", bold=True, size=9),
}


def _thin_border():
    s = Side(style="thin", color=C_BORDER)
    return Border(left=s, right=s, top=s, bottom=s)


def _header_fill():
    return PatternFill("solid", fgColor=C_DARK)


def _header_font():
    return Font(color=C_WHITE, bold=True, size=10)


def _center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def _vcenter():
    return Alignment(vertical="center")


# ── Sheet: Leads ──────────────────────────────────────────────────────────────
COLUMNS = [
    ("Company Name",  28),
    ("Website",       30),
    ("Contact Name",  20),
    ("Title",         22),
    ("Email",         28),
    ("Phone",         16),
    ("Location",      18),
    ("Company Size",  14),
    ("LinkedIn",      36),
    ("Status",        14),
]


def _write_leads_sheet(ws, leads: list[dict]) -> None:
    ws.title = "Leads"
    ws.freeze_panes = "A2"
    ws.sheet_view.showGridLines = False

    # Header row
    for col_idx, (col_name, col_w) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.fill   = _header_fill()
        cell.font   = _header_font()
        cell.alignment = _center()
        cell.border = _thin_border()
        ws.column_dimensions[get_column_letter(col_idx)].width = col_w

    ws.row_dimensions[1].height = 28

    col_names = [c[0] for c in COLUMNS]
    alt_fill  = PatternFill("solid", fgColor=C_ROW_ALT)
    white_fill = PatternFill("solid", fgColor=C_WHITE)

    for row_idx, lead in enumerate(leads, start=2):
        row_fill = alt_fill if row_idx % 2 == 0 else white_fill
        for col_idx, col_name in enumerate(col_names, start=1):
            value = lead.get(col_name, "N/A")
            cell  = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border    = _thin_border()
            cell.alignment = _vcenter() if col_name != "Status" else _center()
            cell.font      = Font(size=9)

            if col_name == "Status":
                cell.fill = STATUS_FILL.get(str(value), row_fill)
                cell.font = STATUS_FONT.get(str(value), Font(size=9))
            elif col_name == "Website":
                cell.font = Font(size=9, color="0563C1", underline="single")
                cell.hyperlink = value if str(value).startswith("http") else None
                cell.fill = row_fill
            elif col_name == "LinkedIn" and str(value) not in ("N/A", ""):
                cell.font = Font(size=9, color="0A66C2", underline="single")  # LinkedIn blue
                cell.hyperlink = value if str(value).startswith("http") else None
                cell.fill = row_fill
            elif col_name == "Email" and str(value) not in ("N/A", ""):
                cell.font = Font(size=9, color="0563C1", underline="single")
                cell.hyperlink = f"mailto:{value}"
                cell.fill = row_fill
            else:
                cell.fill = row_fill

        ws.row_dimensions[row_idx].height = 18

    # Auto-filter
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}1"


# ── Sheet: Summary ────────────────────────────────────────────────────────────
def _write_summary_sheet(ws, leads: list[dict], criteria: dict) -> None:
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False

    # ── Title banner ──────────────────────────────────────────────────────────
    ws.merge_cells("A1:H1")
    title_cell = ws["A1"]
    title_cell.value     = "Lead Generation Report"
    title_cell.fill      = _header_fill()
    title_cell.font      = Font(color=C_WHITE, bold=True, size=16)
    title_cell.alignment = _center()
    ws.row_dimensions[1].height = 40

    # ── Criteria block ────────────────────────────────────────────────────────
    def _kv(row, key, val):
        k = ws.cell(row=row, column=1, value=key)
        k.font      = Font(bold=True, size=9, color=C_DARK)
        k.alignment = _vcenter()
        k.fill      = PatternFill("solid", fgColor=C_ROW_ALT)
        k.border    = _thin_border()
        v = ws.cell(row=row, column=2, value=val)
        v.font      = Font(size=9)
        v.alignment = _vcenter()
        v.fill      = PatternFill("solid", fgColor=C_WHITE)
        v.border    = _thin_border()
        ws.row_dimensions[row].height = 18

    crit_items = [
        ("Industry",     criteria.get("industry", "—")),
        ("Location",     criteria.get("location", "—")),
        ("Target Role",  criteria.get("target_role", "—")),
        ("Company Size", criteria.get("company_size", "—")),
        ("Lead Type",    criteria.get("lead_type", "—")),
        ("Keywords",     criteria.get("keywords") or "—"),
    ]
    for i, (k, v) in enumerate(crit_items, start=2):
        _kv(i, k, v)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 24

    # ── KPI cards ─────────────────────────────────────────────────────────────
    total    = len(leads)
    verified = sum(1 for l in leads if l.get("Status") == "Verified")
    new_     = sum(1 for l in leads if l.get("Status") == "New")
    missing  = sum(1 for l in leads if l.get("Status") == "Missing Email")

    kpis = [
        ("Total Leads",    total,    C_DARK),
        ("Verified",       verified, C_GREEN),
        ("New",            new_,     C_MID),
        ("Missing Email",  missing,  C_LIGHT),
    ]
    kpi_row = len(crit_items) + 3
    ws.row_dimensions[kpi_row - 1].height = 10  # spacer
    for col_offset, (label, val, color) in enumerate(kpis):
        col = col_offset * 2 + 1
        # Value cell
        vc = ws.cell(row=kpi_row, column=col, value=val)
        vc.fill      = PatternFill("solid", fgColor=color)
        vc.font      = Font(color=C_WHITE if color != C_LIGHT else "444444",
                            bold=True, size=20)
        vc.alignment = _center()
        vc.border    = _thin_border()
        ws.merge_cells(
            start_row=kpi_row, start_column=col,
            end_row=kpi_row, end_column=col + 1
        )
        ws.row_dimensions[kpi_row].height = 44

        # Label cell
        lc = ws.cell(row=kpi_row + 1, column=col, value=label)
        lc.fill      = PatternFill("solid", fgColor=color)
        lc.font      = Font(color=C_WHITE if color != C_LIGHT else "444444",
                            bold=True, size=9)
        lc.alignment = _center()
        lc.border    = _thin_border()
        ws.merge_cells(
            start_row=kpi_row + 1, start_column=col,
            end_row=kpi_row + 1, end_column=col + 1
        )
        ws.row_dimensions[kpi_row + 1].height = 22
        ws.column_dimensions[get_column_letter(col)].width = 14
        ws.column_dimensions[get_column_letter(col + 1)].width = 14

    # ── Stats table (used by charts) ──────────────────────────────────────────
    stats_row = kpi_row + 4
    ws.row_dimensions[stats_row - 1].height = 10  # spacer

    for r, (label, val) in enumerate([
        ("Verified",      verified),
        ("New",           new_),
        ("Missing Email", missing),
    ], start=stats_row):
        ws.cell(row=r, column=1, value=label).font = Font(size=9, bold=True)
        ws.cell(row=r, column=2, value=val).font   = Font(size=9)
        ws.row_dimensions[r].height = 16

    # ── Pie chart: status breakdown ───────────────────────────────────────────
    pie = PieChart()
    pie.title  = "Lead Status Breakdown"
    pie.style  = 10
    pie.width  = 14
    pie.height = 10

    data_ref  = Reference(ws, min_col=2, min_row=stats_row,
                          max_row=stats_row + 2)
    label_ref = Reference(ws, min_col=1, min_row=stats_row,
                          max_row=stats_row + 2)
    pie.add_data(data_ref)
    pie.set_categories(label_ref)
    pie.series[0].title = None

    # Colour each slice to match brand palette
    slice_colors = [C_GREEN, C_MID, C_LIGHT]
    for idx, color in enumerate(slice_colors):
        pt = DataPoint(idx=idx)
        pt.graphicalProperties.solidFill = color
        pie.series[0].dPt.append(pt)

    ws.add_chart(pie, f"D{kpi_row - 1}")

    # ── Bar chart: company-size breakdown ─────────────────────────────────────
    size_counts: dict[str, int] = {}
    for lead in leads:
        sz = str(lead.get("Company Size") or "N/A").strip()
        size_counts[sz] = size_counts.get(sz, 0) + 1

    size_row = stats_row + 5
    ws.row_dimensions[size_row - 1].height = 10
    ws.cell(row=size_row - 1, column=1, value="Company Size").font = Font(
        bold=True, size=9, color=C_DARK
    )
    for r, (sz, cnt) in enumerate(size_counts.items(), start=size_row):
        ws.cell(row=r, column=1, value=sz).font  = Font(size=9)
        ws.cell(row=r, column=2, value=cnt).font = Font(size=9)
        ws.row_dimensions[r].height = 16

    if size_counts:
        bar = BarChart()
        bar.type    = "col"
        bar.style   = 10
        bar.title   = "Company Size Distribution"
        bar.y_axis.title = "Count"
        bar.width   = 14
        bar.height  = 10

        bar_data  = Reference(ws, min_col=2, min_row=size_row,
                              max_row=size_row + len(size_counts) - 1)
        bar_cats  = Reference(ws, min_col=1, min_row=size_row,
                              max_row=size_row + len(size_counts) - 1)
        bar.add_data(bar_data)
        bar.set_categories(bar_cats)
        bar.series[0].graphicalProperties.solidFill  = C_DARK
        bar.series[0].graphicalProperties.line.solidFill = C_DARK

        ws.add_chart(bar, f"D{kpi_row + 8}")


# ── Public API ────────────────────────────────────────────────────────────────
def build_excel(leads: list[dict], criteria: dict | None = None) -> bytes:
    """
    Returns the raw bytes of a formatted .xlsx file.
    `criteria` is the SearchCriteria dict (for the summary sheet header).
    """
    wb = Workbook()
    ws_summary = wb.active
    ws_leads   = wb.create_sheet()

    _write_summary_sheet(ws_summary, leads, criteria or {})
    _write_leads_sheet(ws_leads, leads)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
