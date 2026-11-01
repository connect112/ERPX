"""
Where students pay by bank transfer or UPI: details entered in an internship's settings, or one of the organization's
saved accounts. Saved accounts are created, edited, verified and switched off only by finance staff (changes are audited
by the ORM hooks); editing the details clears the verification, and students only ever see an enabled, verified account.
The UPI QR code is generated for each student from the configured UPI ID and the amount they owe.
"""

import base64
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote

import qrcode
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.authentication.models import User
from modules.internship_onboarding.config import BankAccount, OnboardingConfig, UpiAccount, masked_accounts
from modules.internship_onboarding.models import PaymentAccount
from modules.internship_onboarding.service import FINANCE_MANAGE, FINANCE_VIEW, has, require

MODELS = {"bank": BankAccount, "upi": UpiAccount}


def _details(kind: str, details: dict) -> dict:
    if kind not in MODELS:
        raise ValidationError("An account is either a bank account or a UPI ID.")
    try:
        return MODELS[kind].model_validate(details).model_dump(mode="json")
    except PydanticValidationError as exc:
        first = exc.errors()[0]
        raise ValidationError(f"{'.'.join(str(p) for p in first['loc']) or 'details'}: {first['msg']}") from None


def _out(account: PaymentAccount, full: bool) -> dict:
    details = account.details if full or account.kind != "bank" else masked_accounts({"bank": account.details})["bank"]
    return {
        "id": account.id, "kind": account.kind, "label": account.label, "details": details, "enabled": account.enabled,
        "verified": account.verified_at is not None, "verified_at": account.verified_at, "updated_at": account.updated_at,
    }  # fmt: skip


class PaymentAccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get(self, organization_id: uuid.UUID, account_id: uuid.UUID) -> PaymentAccount:
        account = await self.db.get(PaymentAccount, account_id)
        if account is None or account.organization_id != organization_id:
            raise NotFoundError("Payment account", account_id)
        return account

    async def list(self, organization_id: uuid.UUID, user: User) -> list[dict]:
        full = await has(self.db, user, FINANCE_MANAGE)
        if not full:
            await require(self.db, user, FINANCE_VIEW)
        rows = await self.db.execute(select(PaymentAccount).where(PaymentAccount.organization_id == organization_id).order_by(PaymentAccount.label))
        return [_out(a, full) for a in rows.scalars()]

    async def _save(self, account: PaymentAccount, new: bool = False) -> dict:
        try:
            async with self.db.begin_nested():  # a refused name leaves nothing behind in the session
                if new:
                    self.db.add(account)
                await self.db.flush()
        except IntegrityError:
            raise ConflictError("Another saved account already has this name.") from None
        await self.db.refresh(account)
        return _out(account, True)

    async def create(self, organization_id: uuid.UUID, user: User, kind: str, label: str, details: dict, enabled: bool) -> dict:
        await require(self.db, user, FINANCE_MANAGE)
        if not label.strip():
            raise ValidationError("Give the account a name staff will recognise.")
        account = PaymentAccount(organization_id=organization_id, kind=kind, label=label.strip()[:80], details=_details(kind, details),
                                 enabled=enabled, updated_by_user_id=user.id)  # fmt: skip
        return await self._save(account, new=True)

    async def update(self, organization_id: uuid.UUID, account_id: uuid.UUID, user: User, label: str | None,
                     details: dict | None, enabled: bool | None) -> dict:  # fmt: skip
        await require(self.db, user, FINANCE_MANAGE)
        account = await self._get(organization_id, account_id)
        if label is not None:
            if not label.strip():
                raise ValidationError("Give the account a name staff will recognise.")
            account.label = label.strip()[:80]
        if details is not None:
            clean = _details(account.kind, details)
            if clean != account.details:
                # new details are not shown to students until someone has checked them again
                account.details, account.verified_at, account.verified_by_user_id = clean, None, None
        if enabled is not None:
            account.enabled = enabled
        account.updated_by_user_id = user.id
        return await self._save(account)

    async def verify(self, organization_id: uuid.UUID, account_id: uuid.UUID, user: User) -> dict:
        """A finance user confirms the details are the organization's own account (e.g. against the bank letter)."""
        await require(self.db, user, FINANCE_MANAGE)
        account = await self._get(organization_id, account_id)
        account.verified_at, account.verified_by_user_id = datetime.now(timezone.utc), user.id
        return await self._save(account)

    async def check_references(self, organization_id: uuid.UUID, config: OnboardingConfig) -> None:
        """Settings may only point at this organization's saved accounts of the right kind that are switched on."""
        for kind, account_id in (("bank", config.payment_accounts.bank_account_id), ("upi", config.payment_accounts.upi_account_id)):
            if account_id is None:
                continue
            account = await self.db.get(PaymentAccount, account_id)
            if account is None or account.organization_id != organization_id or account.kind != kind:
                raise ValidationError(f"The chosen saved {'bank account' if kind == 'bank' else 'UPI ID'} does not exist.")
            if not account.enabled:
                raise ValidationError(f'The saved account "{account.label}" is switched off.')

    async def for_students(self, organization_id: uuid.UUID, config: OnboardingConfig) -> dict[str, dict | None]:
        """The details a student may see for each enabled method: entered in the settings, or a saved account that is
        enabled and verified. A method whose details are not usable is simply not offered."""
        accounts = config.payment_accounts
        out: dict[str, dict | None] = {"bank": None, "upi": None}
        for kind, method, inline, account_id in (("bank", "bank_transfer", accounts.bank, accounts.bank_account_id),
                                                 ("upi", "upi", accounts.upi, accounts.upi_account_id)):  # fmt: skip
            if method not in config.fees.methods:
                continue
            if inline is not None:
                out[kind] = inline.model_dump(mode="json")
            elif account_id is not None:
                account = await self.db.get(PaymentAccount, account_id)
                if account and account.organization_id == organization_id and account.kind == kind and account.enabled and account.verified_at:
                    out[kind] = dict(account.details)
        return out


def upi_link(upi: dict, amount: Decimal, note: str) -> str:
    """A UPI payment link (NPCI ``upi://pay``) for exactly what the student owes, with their reference as the note."""
    return (
        f"upi://pay?pa={quote(upi['vpa'], safe='@')}&pn={quote(upi['beneficiary'])}&am={amount:.2f}&cu=INR&tn={quote(note[:50])}"
    )


def qr_png_data_url(text: str) -> str:
    image = qrcode.make(text, box_size=6, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
