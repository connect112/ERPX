from pydantic import BaseModel


class HealthCheckResult(BaseModel):
    component: str
    status: str
    latency_ms: float | None
    detail: str | None
    message: str | None


class SystemHealthResponse(BaseModel):
    overall_status: str
    checks: list[HealthCheckResult]


class PlatformStatsResponse(BaseModel):
    organization_count: int
    user_count: int
    student_count: int
    audit_events_last_24h: int
