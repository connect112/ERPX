"""create corporate tables (clients, projects, quotations, contracts, tickets, amc, vapt, soc)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

corporate_client_status_enum = postgresql.ENUM("prospect", "active", "inactive", "churned", name="corporate_client_status")
corporate_project_type_enum = postgresql.ENUM("vapt", "soc", "consulting", "training", "other", name="corporate_project_type")
corporate_project_status_enum = postgresql.ENUM("planned", "in_progress", "on_hold", "completed", "cancelled", name="corporate_project_status")
quotation_status_enum = postgresql.ENUM("draft", "sent", "accepted", "rejected", "expired", name="quotation_status")
corporate_contract_type_enum = postgresql.ENUM("project", "amc", "retainer", "soc_subscription", "other", name="corporate_contract_type")
corporate_contract_status_enum = postgresql.ENUM("draft", "active", "expired", "terminated", "renewed", name="corporate_contract_status")
amc_billing_frequency_enum = postgresql.ENUM("monthly", "quarterly", "annually", name="amc_billing_frequency")
amc_status_enum = postgresql.ENUM("active", "expired", "renewed", "cancelled", name="amc_status")
amc_visit_status_enum = postgresql.ENUM("scheduled", "completed", "cancelled", name="amc_visit_status")
ticket_priority_enum = postgresql.ENUM("low", "medium", "high", "urgent", name="ticket_priority")
ticket_status_enum = postgresql.ENUM("open", "in_progress", "on_hold", "resolved", "closed", name="ticket_status")
vapt_engagement_type_enum = postgresql.ENUM("web_app", "mobile_app", "network", "cloud", "api", "red_team", "other", name="vapt_engagement_type")
vapt_engagement_status_enum = postgresql.ENUM("scoping", "in_progress", "reporting", "retest", "closed", name="vapt_engagement_status")
vapt_finding_severity_enum = postgresql.ENUM("critical", "high", "medium", "low", "informational", name="vapt_finding_severity")
vapt_finding_status_enum = postgresql.ENUM("open", "retesting", "fixed", "accepted_risk", "false_positive", name="vapt_finding_status")
soc_service_type_enum = postgresql.ENUM("monitoring", "incident_response", "threat_hunting", "log_management", name="soc_service_type")
soc_service_status_enum = postgresql.ENUM("active", "suspended", "terminated", name="soc_service_status")
soc_incident_severity_enum = postgresql.ENUM("critical", "high", "medium", "low", name="soc_incident_severity")
soc_incident_status_enum = postgresql.ENUM("open", "investigating", "contained", "resolved", "closed", name="soc_incident_status")

_ALL_ENUMS = [
    corporate_client_status_enum,
    corporate_project_type_enum,
    corporate_project_status_enum,
    quotation_status_enum,
    corporate_contract_type_enum,
    corporate_contract_status_enum,
    amc_billing_frequency_enum,
    amc_status_enum,
    amc_visit_status_enum,
    ticket_priority_enum,
    ticket_status_enum,
    vapt_engagement_type_enum,
    vapt_engagement_status_enum,
    vapt_finding_severity_enum,
    vapt_finding_status_enum,
    soc_service_type_enum,
    soc_service_status_enum,
    soc_incident_severity_enum,
    soc_incident_status_enum,
]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Clients ----
    op.create_table(
        "corporate_clients",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accounting_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_manager_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=150), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("contact_person_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("status", postgresql.ENUM("prospect", "active", "inactive", "churned", name="corporate_client_status", create_type=False), nullable=False, server_default="prospect"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "client_code", name="uq_corporate_client_org_code"),
    )
    op.create_index("ix_corporate_clients_organization_id", "corporate_clients", ["organization_id"])
    op.create_index("ix_corporate_clients_accounting_customer_id", "corporate_clients", ["accounting_customer_id"])
    op.create_index("ix_corporate_clients_status", "corporate_clients", ["status"])

    # ---- Projects ----
    op.create_table(
        "corporate_projects",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_manager_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_type", postgresql.ENUM("vapt", "soc", "consulting", "training", "other", name="corporate_project_type", create_type=False), nullable=False, server_default="other"),
        sa.Column("status", postgresql.ENUM("planned", "in_progress", "on_hold", "completed", "cancelled", name="corporate_project_status", create_type=False), nullable=False, server_default="planned"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("budget_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "project_code", name="uq_corporate_project_org_code"),
    )
    op.create_index("ix_corporate_projects_organization_id", "corporate_projects", ["organization_id"])
    op.create_index("ix_corporate_projects_client_id", "corporate_projects", ["client_id"])
    op.create_index("ix_corporate_projects_project_type", "corporate_projects", ["project_type"])
    op.create_index("ix_corporate_projects_status", "corporate_projects", ["status"])

    # ---- Quotations ----
    op.create_table(
        "corporate_quotations",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quotation_number", sa.String(length=50), nullable=False),
        sa.Column("quotation_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "sent", "accepted", "rejected", "expired", name="quotation_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("subtotal_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "quotation_number", name="uq_quotation_org_number"),
    )
    op.create_index("ix_corporate_quotations_organization_id", "corporate_quotations", ["organization_id"])
    op.create_index("ix_corporate_quotations_client_id", "corporate_quotations", ["client_id"])
    op.create_index("ix_corporate_quotations_quotation_date", "corporate_quotations", ["quotation_date"])
    op.create_index("ix_corporate_quotations_status", "corporate_quotations", ["status"])

    op.create_table(
        "corporate_quotation_lines",
        *_tc(),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_quotations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gst_rate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_corporate_quotation_lines_quotation_id", "corporate_quotation_lines", ["quotation_id"])

    # ---- Contracts ----
    op.create_table(
        "corporate_contracts",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_quotations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contract_number", sa.String(length=50), nullable=False),
        sa.Column("contract_type", postgresql.ENUM("project", "amc", "retainer", "soc_subscription", "other", name="corporate_contract_type", create_type=False), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("contract_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "active", "expired", "terminated", "renewed", name="corporate_contract_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("signed_date", sa.Date(), nullable=True),
        sa.Column("document_url", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "contract_number", name="uq_contract_org_number"),
    )
    op.create_index("ix_corporate_contracts_organization_id", "corporate_contracts", ["organization_id"])
    op.create_index("ix_corporate_contracts_client_id", "corporate_contracts", ["client_id"])
    op.create_index("ix_corporate_contracts_status", "corporate_contracts", ["status"])

    # ---- AMC ----
    op.create_table(
        "corporate_amc_contracts",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_contracts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amc_number", sa.String(length=50), nullable=False),
        sa.Column("coverage_description", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("renewal_reminder_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("billing_frequency", postgresql.ENUM("monthly", "quarterly", "annually", name="amc_billing_frequency", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("active", "expired", "renewed", "cancelled", name="amc_status", create_type=False), nullable=False, server_default="active"),
        sa.UniqueConstraint("organization_id", "amc_number", name="uq_amc_contract_org_number"),
    )
    op.create_index("ix_corporate_amc_contracts_organization_id", "corporate_amc_contracts", ["organization_id"])
    op.create_index("ix_corporate_amc_contracts_client_id", "corporate_amc_contracts", ["client_id"])
    op.create_index("ix_corporate_amc_contracts_end_date", "corporate_amc_contracts", ["end_date"])
    op.create_index("ix_corporate_amc_contracts_status", "corporate_amc_contracts", ["status"])

    op.create_table(
        "corporate_amc_visits",
        *_tc(),
        sa.Column("amc_contract_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_amc_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engineer_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("purpose", sa.String(length=500), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM("scheduled", "completed", "cancelled", name="amc_visit_status", create_type=False), nullable=False, server_default="scheduled"),
    )
    op.create_index("ix_corporate_amc_visits_amc_contract_id", "corporate_amc_visits", ["amc_contract_id"])
    op.create_index("ix_corporate_amc_visits_visit_date", "corporate_amc_visits", ["visit_date"])
    op.create_index("ix_corporate_amc_visits_status", "corporate_amc_visits", ["status"])

    # ---- Tickets ----
    op.create_table(
        "corporate_support_tickets",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ticket_number", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", postgresql.ENUM("low", "medium", "high", "urgent", name="ticket_priority", create_type=False), nullable=False, server_default="medium"),
        sa.Column("status", postgresql.ENUM("open", "in_progress", "on_hold", "resolved", "closed", name="ticket_status", create_type=False), nullable=False, server_default="open"),
        sa.Column("raised_by_contact_name", sa.String(length=255), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "ticket_number", name="uq_support_ticket_org_number"),
    )
    op.create_index("ix_corporate_support_tickets_organization_id", "corporate_support_tickets", ["organization_id"])
    op.create_index("ix_corporate_support_tickets_client_id", "corporate_support_tickets", ["client_id"])
    op.create_index("ix_corporate_support_tickets_assigned_to_employee_id", "corporate_support_tickets", ["assigned_to_employee_id"])
    op.create_index("ix_corporate_support_tickets_priority", "corporate_support_tickets", ["priority"])
    op.create_index("ix_corporate_support_tickets_status", "corporate_support_tickets", ["status"])

    op.create_table(
        "corporate_ticket_comments",
        *_tc(),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_support_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_corporate_ticket_comments_ticket_id", "corporate_ticket_comments", ["ticket_id"])

    # ---- VAPT ----
    op.create_table(
        "corporate_vapt_engagements",
        *_tc(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_tester_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("engagement_type", postgresql.ENUM("web_app", "mobile_app", "network", "cloud", "api", "red_team", "other", name="vapt_engagement_type", create_type=False), nullable=False),
        sa.Column("methodology", sa.String(length=255), nullable=True),
        sa.Column("status", postgresql.ENUM("scoping", "in_progress", "reporting", "retest", "closed", name="vapt_engagement_status", create_type=False), nullable=False, server_default="scoping"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_corporate_vapt_engagements_project_id", "corporate_vapt_engagements", ["project_id"])
    op.create_index("ix_corporate_vapt_engagements_status", "corporate_vapt_engagements", ["status"])

    op.create_table(
        "corporate_vapt_findings",
        *_tc(),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_vapt_engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("severity", postgresql.ENUM("critical", "high", "medium", "low", "informational", name="vapt_finding_severity", create_type=False), nullable=False),
        sa.Column("cvss_score", sa.Numeric(3, 1), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM("open", "retesting", "fixed", "accepted_risk", "false_positive", name="vapt_finding_status", create_type=False), nullable=False, server_default="open"),
        sa.Column("reported_date", sa.Date(), nullable=False),
        sa.Column("closed_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_corporate_vapt_findings_engagement_id", "corporate_vapt_findings", ["engagement_id"])
    op.create_index("ix_corporate_vapt_findings_severity", "corporate_vapt_findings", ["severity"])
    op.create_index("ix_corporate_vapt_findings_status", "corporate_vapt_findings", ["status"])

    # ---- SOC ----
    op.create_table(
        "corporate_soc_services",
        *_tc(),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_type", postgresql.ENUM("monitoring", "incident_response", "threat_hunting", "log_management", name="soc_service_type", create_type=False), nullable=False),
        sa.Column("sla_response_time_minutes", sa.Integer(), nullable=True),
        sa.Column("status", postgresql.ENUM("active", "suspended", "terminated", name="soc_service_status", create_type=False), nullable=False, server_default="active"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_corporate_soc_services_client_id", "corporate_soc_services", ["client_id"])
    op.create_index("ix_corporate_soc_services_status", "corporate_soc_services", ["status"])

    op.create_table(
        "corporate_soc_incidents",
        *_tc(),
        sa.Column("soc_service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("corporate_soc_services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_to_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("severity", postgresql.ENUM("critical", "high", "medium", "low", name="soc_incident_severity", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM("open", "investigating", "contained", "resolved", "closed", name="soc_incident_status", create_type=False), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_corporate_soc_incidents_soc_service_id", "corporate_soc_incidents", ["soc_service_id"])
    op.create_index("ix_corporate_soc_incidents_severity", "corporate_soc_incidents", ["severity"])
    op.create_index("ix_corporate_soc_incidents_status", "corporate_soc_incidents", ["status"])
    op.create_index("ix_corporate_soc_incidents_detected_at", "corporate_soc_incidents", ["detected_at"])


def downgrade() -> None:
    op.drop_table("corporate_soc_incidents")
    op.drop_table("corporate_soc_services")
    op.drop_table("corporate_vapt_findings")
    op.drop_table("corporate_vapt_engagements")
    op.drop_table("corporate_ticket_comments")
    op.drop_table("corporate_support_tickets")
    op.drop_table("corporate_amc_visits")
    op.drop_table("corporate_amc_contracts")
    op.drop_table("corporate_contracts")
    op.drop_table("corporate_quotation_lines")
    op.drop_table("corporate_quotations")
    op.drop_table("corporate_projects")
    op.drop_table("corporate_clients")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
