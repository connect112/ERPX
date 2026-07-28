import uuid
from datetime import date

from pydantic import BaseModel


class ClientSummaryResponse(BaseModel):
    client_id: uuid.UUID
    total_projects: int
    active_projects: int
    open_tickets: int
    active_amc_contracts: int
    active_soc_services: int
    active_contract_value: float


class VAPTPortfolioSummaryResponse(BaseModel):
    as_of_date: date
    total_engagements: int
    total_findings: int
    open_findings: int
    findings_by_severity: dict[str, int]


class TicketSLASummaryResponse(BaseModel):
    open_tickets: int
    overdue_tickets: int
    by_priority: dict[str, int]


class MessageResponse(BaseModel):
    message: str
