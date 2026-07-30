"""
Service tests for Corporate Reports > VAPT portfolio summary.

The summary is assembled with grouped SQL aggregation (a single engagement
count-join plus a single severity/status breakdown-join over
findings → engagements → projects) rather than a per-project/per-engagement
fetch-and-loop. Each test asserts the returned figures equal the manual
counts over seeded data and pins the VAPT-table query count to guard against
the triple-nested N+1 being reintroduced.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import event

from modules.corporate.clients.repository import ClientRepository
from modules.corporate.projects.models import ProjectType
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.vapt.models import FindingSeverity, FindingStatus, VAPTEngagementType
from modules.corporate.vapt.repository import VAPTEngagementRepository, VAPTFindingRepository
from modules.corporate.reports.service import CorporateReportService

pytestmark = pytest.mark.api

_SEVERITIES = list(FindingSeverity)
_VAPT_TABLES = ("corporate_vapt_engagements", "corporate_vapt_findings", "corporate_projects")


class _VaptQueryCounter:
    def __init__(self):
        from app.db.session import engine

        self._engine = engine.sync_engine
        self.count = 0

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._on)

    def _on(self, conn, cursor, statement, params, context, executemany):
        s = statement.lower()
        if any(table in s for table in _VAPT_TABLES):
            self.count += 1


def _vapt_project_type():
    return getattr(ProjectType, "VAPT", None) or _SEVERITIES and list(ProjectType)[0]


async def _seed(db_session, organization, *, n_projects=3, eng_each=2, find_each=4):
    client = await ClientRepository(db_session).create(
        organization_id=organization.id, client_code=f"CL-{uuid.uuid4().hex[:6]}", name="Acme Corp",
    )
    proj_repo = ProjectRepository(db_session)
    eng_repo = VAPTEngagementRepository(db_session)
    find_repo = VAPTFindingRepository(db_session)
    expected = {"engagements": 0, "findings": 0, "open": 0, "by_sev": {s.value: 0 for s in _SEVERITIES}}
    k = 0
    for i in range(n_projects):
        project = await proj_repo.create(
            organization_id=organization.id, client_id=client.id,
            project_code=f"P-{uuid.uuid4().hex[:6]}", name=f"Project {i}",
            project_type=list(ProjectType)[0], start_date=date(2026, 1, 1),
        )
        for _ in range(eng_each):
            engagement = await eng_repo.create(
                project_id=project.id, scope_description="scope",
                engagement_type=VAPTEngagementType.WEB_APP, start_date=date(2026, 1, 2),
            )
            expected["engagements"] += 1
            for _ in range(find_each):
                severity = _SEVERITIES[k % len(_SEVERITIES)]
                status = FindingStatus.OPEN if k % 3 == 0 else FindingStatus.FIXED
                await find_repo.create(
                    engagement_id=engagement.id, title="finding", severity=severity,
                    description="d", recommendation="r", status=status, reported_date=date(2026, 1, 3),
                )
                expected["findings"] += 1
                expected["by_sev"][severity.value] += 1
                if status in {FindingStatus.OPEN, FindingStatus.RETESTING}:
                    expected["open"] += 1
                k += 1
    await db_session.flush()
    return expected


async def test_vapt_portfolio_summary_is_sql_aggregated(db_session, organization):
    expected = await _seed(db_session, organization)

    with _VaptQueryCounter() as counter:
        result = await CorporateReportService(db_session).vapt_portfolio_summary(
            organization.id, date(2026, 7, 30)
        )

    assert result["total_engagements"] == expected["engagements"]
    assert result["total_findings"] == expected["findings"]
    assert result["open_findings"] == expected["open"]
    assert result["findings_by_severity"] == expected["by_sev"]
    # Every severity key is always present (callers seed zeros).
    assert set(result["findings_by_severity"]) == {s.value for s in _SEVERITIES}
    assert result["as_of_date"] == date(2026, 7, 30)
    # One engagement count-join + one findings breakdown-join, not 1 + P + E.
    assert counter.count == 2


async def test_vapt_portfolio_summary_empty_org_is_all_zero(db_session, organization):
    with _VaptQueryCounter() as counter:
        result = await CorporateReportService(db_session).vapt_portfolio_summary(
            organization.id, date(2026, 7, 30)
        )

    assert result["total_engagements"] == 0
    assert result["total_findings"] == 0
    assert result["open_findings"] == 0
    assert result["findings_by_severity"] == {s.value: 0 for s in _SEVERITIES}
    assert counter.count == 2
