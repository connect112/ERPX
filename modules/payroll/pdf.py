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
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.employees.models import Employee
from modules.hr.models import Department, Designation
from modules.organizations.models import Organization
from modules.payroll.models import Payslip, PayrollRun, SalaryComponentType

_STATIC_DIR = Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "static" / "payroll"
_STAMP_PATH = _STATIC_DIR / "stamp.png"
_SIGNATURE_PATH = _STATIC_DIR / "signature.png"

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


def _money(value) -> str:
    return f"{float(value):,.2f}"


def generate_payslip_pdf(
    payslip: Payslip,
    payroll_run: PayrollRun,
    employee: Employee,
    organization: Organization,
    designation: Designation | None,
    department: Department | None,
    component_names: dict,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#4b5563"))
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], fontSize=6.5, textColor=colors.HexColor("#6b7280"), leading=9
    )

    elements = [
        Paragraph(organization.name, styles["Title"]),
        Paragraph(
            f"Payslip for {_MONTH_NAMES[payroll_run.period_month - 1]} {payroll_run.period_year}",
            styles["Heading3"],
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

    earnings = [line for line in payslip.lines if line.component_type == SalaryComponentType.EARNING]
    deductions = [line for line in payslip.lines if line.component_type == SalaryComponentType.DEDUCTION]

    max_rows = max(len(earnings), len(deductions), 1)
    breakdown_rows = [["Earnings", "Amount", "Deductions", "Amount"]]
    for i in range(max_rows):
        earning_name = component_names.get(earnings[i].salary_component_id, "—") if i < len(earnings) else ""
        earning_amount = _money(earnings[i].amount) if i < len(earnings) else ""
        deduction_name = component_names.get(deductions[i].salary_component_id, "—") if i < len(deductions) else ""
        deduction_amount = _money(deductions[i].amount) if i < len(deductions) else ""
        breakdown_rows.append([earning_name, earning_amount, deduction_name, deduction_amount])
    breakdown_rows.append(
        ["Gross", _money(payslip.gross_amount), "Total deductions", _money(payslip.total_deductions)]
    )

    breakdown_table = Table(breakdown_rows, colWidths=[2.15 * inch, 1.35 * inch, 2.15 * inch, 1.35 * inch])
    breakdown_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#1f2937")),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(breakdown_table)
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
    elements.append(Spacer(1, 0.5 * inch))

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
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(_AUTHENTICITY_NOTICE, disclaimer_style))

    doc.build(elements)
    return buffer.getvalue()
