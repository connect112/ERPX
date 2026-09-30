"""
Payslip PDF generation.

A payslip is a single formatted document (company header, employee
details, an earnings/deductions breakdown, and a signed-and-sealed
footer) -- fundamentally different from packages.reports.exporters'
generic "table of rows" export, so it gets its own builder here rather
than being forced through that shared tabular engine.
"""

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.employees.models import Employee
from modules.hr.models import Department, Designation
from modules.organizations.models import Organization
from modules.payroll.models import Payslip, PayrollRun, SalaryComponent, SalaryComponentType

_STATIC_DIR = Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "static" / "payroll"
_STAMP_PATH = _STATIC_DIR / "stamp.png"
_SIGNATURE_PATH = _STATIC_DIR / "signature.png"
_LOGO_PATH = _STATIC_DIR / "logo.png"

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Shown once at the bottom of every payslip: makes a lifted signature/seal
# image useless as "proof" on any other document, without withholding the
# seal itself (an unsigned/unsealed payslip reads as informal/unofficial).
# Wording approved by GIR Technologies for this exact purpose.
_AUTHENTICITY_NOTICE = (
    "This is a system-generated payslip. The signature and company seal shown are for "
    "authentication of this document only and are not valid for any other purpose. Any "
    "unauthorized reproduction or use of this seal/signature outside this document may "
    "result in legal action."
)

_DISCREPANCY_NOTICE = (
    "This payslip is generated based on the attendance and salary structure on record as "
    "of the date of issue. Please report any discrepancy to HR within 7 working days."
)


def _money(value) -> str:
    return f"{float(value):,.2f}"


def _make_footer_drawer(disclaimer_style: ParagraphStyle, left_margin: float, right_margin: float, page_width: float):
    """Anchors the disclaimer to the physical bottom of every page,
    regardless of how much content precedes it -- a payslip short enough
    to leave blank space at the bottom of the page must not leave the
    disclaimer floating in that gap instead of at the actual page edge."""
    available_width = page_width - left_margin - right_margin
    para = Paragraph(_AUTHENTICITY_NOTICE, disclaimer_style)
    _, para_height = para.wrap(available_width, 1 * inch)

    def draw(canvas, doc):
        canvas.saveState()
        para.drawOn(canvas, left_margin, 0.35 * inch)
        canvas.restoreState()

    return draw, para_height


def generate_payslip_pdf(
    payslip: Payslip,
    payroll_run: PayrollRun,
    employee: Employee,
    organization: Organization,
    designation: Designation | None,
    department: Department | None,
    component_names: dict,
    all_components: list[SalaryComponent],
) -> bytes:
    buffer = io.BytesIO()
    left_margin = right_margin = 0.7 * inch
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=1.0 * inch,
        leftMargin=left_margin, rightMargin=right_margin,
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#4b5563"))
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], fontSize=6.5, textColor=colors.HexColor("#6b7280"), leading=9
    )
    draw_footer, _ = _make_footer_drawer(disclaimer_style, left_margin, right_margin, letter[0])
    centered_title = ParagraphStyle("CenteredTitle", parent=styles["Title"], alignment=TA_CENTER)
    centered_subtitle = ParagraphStyle("CenteredSubtitle", parent=styles["Heading3"], alignment=TA_CENTER)

    elements = []
    if _LOGO_PATH.exists():
        logo = Image(str(_LOGO_PATH), width=0.7 * inch, height=0.7 * inch)
        logo.hAlign = "CENTER"
        elements.append(logo)
        elements.append(Spacer(1, 0.05 * inch))
    elements.append(Paragraph(organization.name, centered_title))

    elements += [
        Paragraph(
            f"Payslip for {_MONTH_NAMES[payroll_run.period_month - 1]} {payroll_run.period_year}",
            centered_subtitle,
        ),
        Spacer(1, 0.15 * inch),
    ]

    info_rows = [
        ["Employee name", employee.full_name, "Employee code", employee.employee_code],
        [
            "Designation",
            designation.title if designation else "—",
            "Department",
            department.name if department else "—",
        ],
        [
            "Date of joining",
            employee.date_of_joining.strftime("%d %b %Y"),
            "Days in month",
            str(payslip.days_in_month),
        ],
        ["Paid days", str(payslip.paid_days), "LOP days", str(payslip.lop_days)],
    ]
    info_table = Table(info_rows, colWidths=[1.3 * inch, 2.2 * inch, 1.3 * inch, 2.2 * inch])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 0.25 * inch))

    # Every earning/deduction component the organization has configured is
    # listed, even ones this payslip has no line for (shown as 0) -- a
    # payslip that silently omits a zero-value line (e.g. no PF deducted
    # this month) reads as incomplete rather than confirming there's
    # nothing owed there.
    amounts_by_component = {line.salary_component_id: line.amount for line in payslip.lines}
    listed_ids: set = set()
    earning_rows: list[tuple[str, object]] = []
    deduction_rows: list[tuple[str, object]] = []
    for component in all_components:
        listed_ids.add(component.id)
        amount = amounts_by_component.get(component.id, 0)
        target = earning_rows if component.component_type == SalaryComponentType.EARNING else deduction_rows
        target.append((component.name, amount))
    for line in payslip.lines:
        if line.salary_component_id in listed_ids:
            continue
        target = earning_rows if line.component_type == SalaryComponentType.EARNING else deduction_rows
        target.append((component_names.get(line.salary_component_id, "—"), line.amount))

    def _section_table(title: str, rows: list[tuple[str, object]], total_label: str, total_amount) -> Table:
        # Earnings and deductions stacked as their own single-column
        # sections, rather than side by side -- padding the shorter side
        # up to match the longer one's row count left visible blank cells.
        data = [[title, "Amount"]] + [[name, _money(amount)] for name, amount in rows]
        data.append([total_label, _money(total_amount)])
        table = Table(data, colWidths=[5.15 * inch, 1.35 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#1f2937")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    elements.append(_section_table("Earnings", earning_rows, "Gross", payslip.gross_amount))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(_section_table("Deductions", deduction_rows, "Total deductions", payslip.total_deductions))
    elements.append(Spacer(1, 0.15 * inch))

    net_table = Table([["Net pay", _money(payslip.net_amount)]], colWidths=[5.65 * inch, 1.35 * inch])
    net_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfdf5")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#10b981")),
            ]
        )
    )
    elements.append(net_table)
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(_DISCREPANCY_NOTICE, small))
    elements.append(Spacer(1, 0.35 * inch))

    stamp_cell = Image(str(_STAMP_PATH), width=0.9 * inch, height=0.9 * inch) if _STAMP_PATH.exists() else ""
    signature_cell = (
        Image(str(_SIGNATURE_PATH), width=1.6 * inch, height=0.7 * inch) if _SIGNATURE_PATH.exists() else ""
    )
    signature_block = Table(
        [[stamp_cell, signature_cell], ["Company seal", "Authorized signatory"]],
        colWidths=[1.5 * inch, 2.0 * inch],
    )
    signature_block.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 1), (-1, 1), 8),
                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#4b5563")),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
            ]
        )
    )
    # Push the signature block to the right side of the page.
    outer = Table([[signature_block]], colWidths=[6.9 * inch])
    outer.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT")]))
    elements.append(outer)

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()
