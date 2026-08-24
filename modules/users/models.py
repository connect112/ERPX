"""
Users module — ORM models.

`UserProfile` extends the Authentication module's `User` (credentials
only) with organizational context: which organization/branch someone
belongs to, their designation, employee code, etc. Kept as a separate
one-to-one table rather than fields on `User` itself so Authentication
stays a pure identity/credential module with no knowledge of tenancy —
Authorization and Users both depend on Authentication, never the reverse.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401  (FK target)


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class UserProfile(TimestampedBase):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Idempotency key for server-to-server account provisioning (e.g. the
    # Pentrix-share -> ERPX internal provisioning endpoint) — the caller's
    # own reference (a Pentrix payment id), so a retried provisioning call
    # is recognized and short-circuited rather than creating a duplicate
    # user. Nullable; unset for ordinary staff/admin profiles.
    external_reference: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )

    employee_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    gender: Mapped[Gender | None] = mapped_column(
        SAEnum(
            Gender,
            name="gender",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=True,
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_of_joining: Mapped[date | None] = mapped_column(Date, nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
