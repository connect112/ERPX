import re
import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.social_media.models import PostFormat, PostStatus, VerificationStatus

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_SLUG = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

CAPTION_LIMIT = 2200  # Instagram's caption limit
HASHTAG_LIMIT = 30  # Instagram's hashtag limit per post
CAROUSEL_MIN, CAROUSEL_MAX = 2, 10


# ---------------- settings ----------------


class Colors(BaseModel):
    background: str
    ink: str
    primary: str
    accent: str
    muted: str

    @field_validator("*")
    @classmethod
    def _hex(cls, value: str) -> str:
        if not _HEX.match(value):
            raise ValueError("Colours must look like #1D4ED8.")
        return value.upper()


class Fonts(BaseModel):
    heading: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=60)


class Brand(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(max_length=120)
    handle: str = Field(default="", max_length=60)
    website: str = Field(default="", max_length=200)
    voice: str = Field(max_length=2000)
    colors: Colors
    colors_confirmed: bool = False
    fonts: Fonts
    logo_key: str | None = None

    @field_validator("website")
    @classmethod
    def _website(cls, value: str) -> str:
        if value and not re.match(r"^https?://[^\s]+$", value):
            raise ValueError("The website must start with http:// or https://")
        return value


class Pillar(BaseModel):
    key: str
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=300)
    share: int = Field(ge=0, le=100)  # the share of posts this pillar should get, in percent
    enabled: bool = True

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not _SLUG.match(value):
            raise ValueError("A pillar key is lowercase letters, digits and underscores.")
        return value


class Persona(BaseModel):
    key: str
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not _SLUG.match(value):
            raise ValueError("A persona key is lowercase letters, digits and underscores.")
        return value


class DesignRules(BaseModel):
    max_headline_words: int = Field(ge=1, le=20)
    max_fonts: int = Field(ge=1, le=3)
    max_cover_text_chars: int = Field(ge=10, le=300)
    min_contrast_ratio: float = Field(ge=3.0, le=21.0)
    one_focal_point: bool = True
    logo_exact_only: bool = True
    forbidden_visuals: list[str] = Field(max_length=40)
    prefer: list[str] = Field(max_length=40)


class Budgets(BaseModel):
    monthly_budget_inr: float = Field(ge=0, le=10_000_000)
    alert_at_percent: int = Field(ge=1, le=100)


class Notifications(BaseModel):
    emails: list[str] = Field(default_factory=list, max_length=10)
    notify_on_failure: bool = True
    notify_on_token_expiry: bool = True

    @field_validator("emails")
    @classmethod
    def _emails(cls, value: list[str]) -> list[str]:
        for email in value:
            if not _EMAIL.match(email):
                raise ValueError(f"'{email}' is not a valid email address.")
        return value


def _short_list(value: list[str], what: str) -> list[str]:
    cleaned = [item.strip() for item in value if item.strip()]
    if any(len(item) > 300 for item in cleaned):
        raise ValueError(f"Each {what} must be 300 characters or fewer.")
    return cleaned


class SettingsUpdate(BaseModel):
    timezone: str | None = None
    publish_mode: Literal["manual", "scheduled"] | None = None
    brand: Brand | None = None
    pillars: list[Pillar] | None = Field(default=None, max_length=20)
    personas: list[Persona] | None = Field(default=None, max_length=10)
    prohibited_claims: list[str] | None = Field(default=None, max_length=50)
    objectives: list[str] | None = Field(default=None, max_length=20)
    design_rules: DesignRules | None = None
    budgets: Budgets | None = None
    notifications: Notifications | None = None
    retention_days: int | None = Field(default=None, ge=30, le=3650)

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError("Choose a valid timezone such as Asia/Kolkata.") from None
        return value

    @field_validator("pillars")
    @classmethod
    def _unique_pillars(cls, value: list[Pillar] | None) -> list[Pillar] | None:
        if value is None:
            return value
        keys = [pillar.key for pillar in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Each content pillar needs its own key.")
        if sum(p.share for p in value if p.enabled) > 100:
            raise ValueError("The shares of the enabled pillars add up to more than 100%.")
        return value

    @field_validator("personas")
    @classmethod
    def _unique_personas(cls, value: list[Persona] | None) -> list[Persona] | None:
        if value is not None and len({p.key for p in value}) != len(value):
            raise ValueError("Each audience persona needs its own key.")
        return value

    @field_validator("prohibited_claims")
    @classmethod
    def _claims(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _short_list(value, "prohibited claim")

    @field_validator("objectives")
    @classmethod
    def _objectives(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _short_list(value, "objective")


class SettingsPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timezone: str
    publish_mode: str
    brand: Brand
    pillars: list[Pillar]
    personas: list[Persona]
    prohibited_claims: list[str]
    objectives: list[str]
    design_rules: DesignRules
    budgets: Budgets
    notifications: Notifications
    retention_days: int


# ---------------- integration ----------------


class CapabilityInfo(BaseModel):
    key: str
    label: str
    api: Literal["supported", "needs_app_review", "restricted", "unavailable"]
    implemented: str  # "phase N" while not built, "yes" when built
    # True only when the real thing has happened with the real account (a post published, a notification received).
    verified_live: bool = False
    # What Instagram answered when the account's permissions were probed.
    live_check: Literal["passed", "needs_app_review", "failed", "not_run"] = "not_run"
    note: str


class AccountPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    username: str | None
    account_type: str | None
    status: str
    scopes: list[str]
    capabilities: dict
    token_expires_at: datetime | None
    connected_at: datetime | None
    last_synced_at: datetime | None
    last_error: str | None
    token_days_left: int | None = None


class IntegrationOverview(BaseModel):
    # None until an account has been connected (Phase 4).
    account: AccountPublic | None
    connected: bool
    capabilities: list[CapabilityInfo]
    setup_steps: list[str]
    # What to paste into the Meta app, and whether this server has what it needs to connect.
    app_configured: bool = False
    redirect_uri: str = ""
    webhook_url: str = ""
    webhook_verify_token_set: bool = False
    scopes_requested: list[str] = []


# ---------------- posts ----------------


class Slide(BaseModel):
    heading: str = Field(default="", max_length=120)
    body: str = Field(default="", max_length=400)
    asset_key: str | None = Field(default=None, max_length=300)
    alt_text: str = Field(default="", max_length=420)


class PostContent(BaseModel):
    hooks: list[str] = Field(default_factory=list, max_length=10)
    headline: str = Field(default="", max_length=120)
    caption: str = Field(default="", max_length=CAPTION_LIMIT)
    cta: str = Field(default="", max_length=200)
    hashtags: list[str] = Field(default_factory=list, max_length=HASHTAG_LIMIT)
    alt_text: str = Field(default="", max_length=420)
    thumbnail_text: str = Field(default="", max_length=120)
    visual_direction: str = Field(default="", max_length=1000)
    asset_key: str | None = Field(default=None, max_length=300)
    slides: list[Slide] = Field(default_factory=list, max_length=CAROUSEL_MAX)

    @field_validator("hashtags")
    @classmethod
    def _hashtags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            tag = tag.strip().lstrip("#")
            if not tag:
                continue
            if not re.match(r"^\w{1,100}$", tag):
                raise ValueError(f"'{tag}' is not a valid hashtag (letters, digits and underscores only).")
            if tag.lower() not in {t.lower() for t in cleaned}:
                cleaned.append(tag)
        return cleaned

    @field_validator("hooks")
    @classmethod
    def _hooks(cls, value: list[str]) -> list[str]:
        return [hook.strip()[:200] for hook in value if hook.strip()]


class Source(BaseModel):
    url: str = Field(max_length=600)
    title: str = Field(default="", max_length=300)
    published_at: str | None = Field(default=None, max_length=40)
    retrieved_at: str | None = Field(default=None, max_length=40)

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        if not re.match(r"^https?://[^\s]+$", value):
            raise ValueError("A source must be an http(s) link.")
        return value


class Warning_(BaseModel):
    severity: Literal["info", "warning", "blocking"] = "warning"
    message: str = Field(max_length=600)
    # Set on warnings the automated checks produce (always starts "chk_"); hand-written ones have none.
    code: str | None = Field(default=None, max_length=50)


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    format: PostFormat = PostFormat.IMAGE
    pillar: str | None = Field(default=None, max_length=50)
    objective: str | None = Field(default=None, max_length=300)
    campaign_id: uuid.UUID | None = None
    content: PostContent = Field(default_factory=PostContent)
    sources: list[Source] = Field(default_factory=list, max_length=20)
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED
    high_risk: bool = False
    time_sensitive: bool = False
    scheduled_at: datetime | None = None


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    format: PostFormat | None = None
    pillar: str | None = Field(default=None, max_length=50)
    objective: str | None = Field(default=None, max_length=300)
    campaign_id: uuid.UUID | None = None
    content: PostContent | None = None
    sources: list[Source] | None = Field(default=None, max_length=20)
    verification_status: VerificationStatus | None = None
    high_risk: bool | None = None
    time_sensitive: bool | None = None
    scheduled_at: datetime | None = None
    clear_schedule: bool = False


class PostTransition(BaseModel):
    action: Literal["submit", "request_changes", "approve", "unapprove", "cancel", "reopen"]
    # An approver confirms they have read the warnings / checked the facts of a high-risk or time-sensitive post.
    acknowledge_warnings: bool = False
    acknowledge_high_risk: bool = False


class PostPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    format: str
    pillar: str | None
    objective: str | None
    campaign_id: uuid.UUID | None
    status: str
    content: PostContent
    sources: list[Source]
    warnings: list[Warning_]
    verification_status: str
    high_risk: bool
    time_sensitive: bool
    scheduled_at: datetime | None
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    published_at: datetime | None
    external_permalink: str | None
    attempt_count: int
    last_error: str | None
    duplicate_of_id: uuid.UUID | None
    generation: dict = Field(default_factory=dict)
    next_attempt_at: datetime | None = None
    external_media_id: str | None = None
    design: dict = Field(default_factory=dict)
    artwork: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    # True when an edit has just withdrawn an earlier approval.
    approval_withdrawn: bool = False


class PostListResponse(BaseModel):
    items: list[PostPublic]
    total: int


# ---------------- overview ----------------


class BriefingItem(BaseModel):
    level: Literal["action", "warning", "info"]
    message: str
    link: str | None = None


class LeadSummary(BaseModel):
    last_30_days: int
    by_status: dict[str, int]
    note: str


class RoadmapItem(BaseModel):
    phase: int
    title: str
    status: Literal["done", "next", "planned"]


class Overview(BaseModel):
    briefing: list[BriefingItem]
    post_counts: dict[str, int]
    awaiting_approval: list[PostPublic]
    leads: LeadSummary
    connected: bool
    roadmap: list[RoadmapItem]


# ---------------- research, studio, usage ----------------


class ResearchItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    url: str
    title: str
    summary: str | None
    published_at: datetime | None
    retrieved_at: datetime
    severity: str | None
    cve_ids: list[str]
    facts: dict
    flags: list[str]
    status: str


class ResearchListResponse(BaseModel):
    items: list[ResearchItemPublic]
    total: int
    # {source: {"label", "last_fetch_at", "ok", "error", "count"}}: when each source was last read and how it went.
    sources: dict[str, dict]


class RefreshResult(BaseModel):
    source: str
    label: str
    skipped: bool
    ok: bool
    new: int
    count: int
    error: str | None


class CveLookup(BaseModel):
    cve: str = Field(pattern=r"(?i)^CVE-\d{4}-\d{4,7}$")


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    format: PostFormat = PostFormat.IMAGE
    pillar: str | None = Field(default=None, max_length=50)
    persona_key: str | None = Field(default=None, max_length=40)
    research_item_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
    notes: str = Field(default="", max_length=500)
    time_sensitive: bool = False


class RegenerateRequest(BaseModel):
    element: Literal["hooks", "headline", "caption", "cta", "hashtags", "thumbnail_text", "visual_direction", "alt_text"]
    instruction: str = Field(default="", max_length=300)


class PillarBalanceOut(BaseModel):
    key: str
    label: str
    target: int
    actual: int
    recent: int


class HistoryOverview(BaseModel):
    pillars: list[PillarBalanceOut]
    posts_considered: int
    suggestions: list[str]


class UsageOverview(BaseModel):
    month_start: datetime
    spent_inr: float
    budget_inr: float
    alert_at_percent: int
    over_budget: bool
    over_alert: bool
    calls: int
    by_kind: dict[str, dict]
    is_estimate: bool
    note: str
    ai_configured: bool
    image_configured: bool = False


# ---------------- artwork, assets, grid ----------------


class Design(BaseModel):
    template: Literal["editorial", "statement", "photo", "screenshot"] = "editorial"
    background_asset_id: uuid.UUID | None = None
    # None = use the default (the pillar's name as the kicker, the post's headline, no supporting line).
    kicker: str | None = Field(default=None, max_length=40)
    headline: str | None = Field(default=None, max_length=120)
    subline: str | None = Field(default=None, max_length=160)
    credit: str | None = Field(default=None, max_length=80)
    show_logo: bool = True
    show_handle: bool = True


class BackgroundRequest(BaseModel):
    direction: str = Field(default="", max_length=200)


class AssetPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    filename: str
    content_type: str
    width: int
    height: int
    bytes_size: int
    alt_text: str
    synthetic: bool
    created_at: datetime
    url: str | None = None
    is_logo: bool = False


class ProofreadIssue(BaseModel):
    text: str
    suggestion: str


class ProofreadResult(BaseModel):
    ok: bool
    issues: list[ProofreadIssue]
    current: bool = True


class GridFinding(BaseModel):
    severity: Literal["info", "warning"]
    code: str
    message: str
    tiles: list[int]


class GridOut(BaseModel):
    tiles: list[dict]
    findings: list[GridFinding]
    verdict: Literal["balanced", "review", "not_enough"]
    live_available: bool
    missing: int
    note: str


# ---------------- scheduling, queue, calendar ----------------


class ScheduleRequest(BaseModel):
    # A time without a zone means the account timezone (Settings).
    scheduled_at: datetime


class ResolveRequest(BaseModel):
    published: bool
    media_id: str | None = Field(default=None, max_length=100)
    permalink: str | None = Field(default=None, max_length=500)

    @field_validator("permalink")
    @classmethod
    def _permalink(cls, value: str | None) -> str | None:
        if value and not re.match(r"^https://[^\s]+$", value):
            raise ValueError("The link must start with https://")
        return value or None


class AttemptPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    attempt_no: int
    status: str
    created_at: datetime
    finished_at: datetime | None
    publish_started_at: datetime | None
    media_id: str | None
    error_kind: str | None
    error: str | None
    http_status: int | None
    caption: str


class ReadinessOut(BaseModel):
    ready: bool
    problems: list[str]
    caption: str
    caption_length: int
    caption_limit: int
    publish_mode: str
    timezone: str
    account_connected: bool
    note: str


class ReconcileOut(BaseModel):
    outcome: Literal["published", "not_published", "unknown"]
    note: str
    post: PostPublic


class QueueItem(BaseModel):
    post: PostPublic
    last_attempt: AttemptPublic | None


class QueueOut(BaseModel):
    items: list[QueueItem]
    timezone: str
    worker_note: str


class CalendarItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    format: str
    pillar: str | None
    scheduled_at: datetime
    local_date: str  # YYYY-MM-DD in the account timezone
    local_time: str  # HH:MM in the account timezone
    thumbnail: str | None
    time_sensitive: bool
    high_risk: bool


class CalendarOut(BaseModel):
    start: str
    end: str
    timezone: str
    publish_mode: str
    items: list[CalendarItem]
    ready_to_schedule: list[CalendarItem]
