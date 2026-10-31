"""Internship onboarding release hardening: the owner's default decisions and the optional virus scanner. No database."""

import asyncio
import struct
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as SettingsError

from app.core.config import settings as app_settings
from app.core.exceptions import ServiceUnavailableError, ValidationError
from modules.internship_onboarding import fees as fee
from modules.internship_onboarding import scan
from modules.internship_onboarding.config import OnboardingConfig
from modules.internship_onboarding.financial import kind_for

# ---------------------------------------------------------------- owner decisions


def test_the_default_fee_is_inr_2000_but_payment_stays_off_until_staff_choose_methods():
    c = OnboardingConfig()
    assert c.fees.currency == "INR" and c.fees.base_amount == Decimal("2000")
    assert fee.snapshot(c.fees)["total"] == "2000.00"
    # bank/UPI need the organization's own account details, so nothing is collected until they are entered
    assert c.modes.require_payment is False and c.fees.methods == []


def test_gir_technologies_issues_plain_receipts_by_default_with_no_tax_details_assumed():
    c = OnboardingConfig()
    assert c.issuer.legal_name == "GIR Technologies"
    assert c.issuer.gstin is None and c.issuer.address == "" and c.fees.tax_mode == "none"
    assert kind_for(SimpleNamespace(kind="payment"), c) == "receipt"


def test_payment_timing_and_lms_access_are_set_per_internship():
    assert OnboardingConfig().modes.payment_order == "after_submission"
    assert OnboardingConfig().modes.lms_access == "manual"
    c = OnboardingConfig.model_validate({
        "modes": {"mode": "hybrid", "payment_order": "after_document_approval", "lms_access": "automatic"},
        "deadlines": {"closes_at": "2026-11-15T23:59:00+05:30"},
    })  # fmt: skip
    assert c.modes.payment_order == "after_document_approval" and c.modes.lms_access == "automatic"


def test_policies_are_empty_until_the_organization_writes_them():
    c = OnboardingConfig()
    assert c.policies.refund_policy == "" and c.policies.identity_document_retention_days is None
    with pytest.raises(SettingsError):
        OnboardingConfig.model_validate({"policies": {"identity_document_retention_days": 0}})


def test_cashfree_is_off_unless_the_installation_enables_it():
    assert app_settings.CASHFREE_ENABLED is False and app_settings.CASHFREE_ALLOW_PRODUCTION is False
    assert app_settings.CLAMAV_ENABLED is False


# ---------------------------------------------------------------- virus scanning (fake clamd)


class FakeClamd:
    def __init__(self, reply: bytes):
        self.reply, self.received, self.command = reply, b"", b""

    async def handle(self, reader, writer):
        self.command = await reader.readuntil(b"\0")
        while True:
            size = struct.unpack(">I", await reader.readexactly(4))[0]
            if size == 0:
                break
            self.received += await reader.readexactly(size)
        writer.write(self.reply)
        await writer.drain()
        writer.close()


@pytest.fixture
async def clamd(monkeypatch):
    servers = []

    async def start(reply: bytes) -> FakeClamd:
        fake = FakeClamd(reply)
        server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
        servers.append(server)
        monkeypatch.setattr(app_settings, "CLAMAV_ENABLED", True)
        monkeypatch.setattr(app_settings, "CLAMAV_HOST", "127.0.0.1")
        monkeypatch.setattr(app_settings, "CLAMAV_PORT", server.sockets[0].getsockname()[1])
        monkeypatch.setattr(app_settings, "CLAMAV_TIMEOUT_SECONDS", 5)
        return fake

    yield start
    for server in servers:
        server.close()


async def test_without_a_scanner_files_are_recorded_as_not_scanned(monkeypatch):
    async def never(*args, **kwargs):
        raise AssertionError("must not connect")

    monkeypatch.setattr(scan, "clamd_instream", never)
    assert await scan.scan(b"%PDF-1.4", "document") == scan.NOT_SCANNED


async def test_a_clean_file_is_streamed_whole_and_recorded_as_clean(clamd):
    fake = await clamd(b"stream: OK\0")
    data = b"%PDF-1.4" + bytes(200_000)  # several INSTREAM chunks
    assert await scan.scan(data, "document") == scan.CLEAN
    assert fake.command == b"zINSTREAM\0" and fake.received == data


async def test_an_infected_file_is_refused(clamd):
    await clamd(b"stream: Eicar-Signature FOUND\0")
    with pytest.raises(ValidationError):
        await scan.scan(b"X5O!P%@AP", "document")


async def test_a_scanner_error_or_an_unreachable_scanner_refuses_the_upload(clamd, monkeypatch):
    await clamd(b"INSTREAM size limit exceeded. ERROR\0")
    with pytest.raises(ServiceUnavailableError):
        await scan.scan(b"%PDF-1.4", "document")
    monkeypatch.setattr(app_settings, "CLAMAV_PORT", 1)  # nothing listens there
    with pytest.raises(ServiceUnavailableError):
        await scan.scan(b"%PDF-1.4", "document")


# ---------------------------------------------------------------- consent and retention safeguards


def _paid_self_service(**over) -> dict:
    base = {
        "modes": {"mode": "hybrid", "require_payment": True},
        "fees": {"methods": ["upi"]},
        "deadlines": {"closes_at": "2026-11-15T23:59:00+05:30"},
        "payment_accounts": {"upi": {"vpa": "test@bank", "beneficiary": "Test"}},
        "policies": {"refund_policy": "Synthetic refund policy."},
    }
    base.update(over)
    return base


def test_students_cannot_pay_through_their_link_without_a_refund_policy():
    OnboardingConfig.model_validate(_paid_self_service())
    with pytest.raises(SettingsError, match="refund policy"):
        OnboardingConfig.model_validate(_paid_self_service(policies={"refund_policy": "   "}))
    # staff-only onboarding and free internships collect no money through the link
    OnboardingConfig.model_validate(_paid_self_service(modes={"mode": "manual", "require_payment": True}, deadlines={}, policies={}))


def test_identity_documents_need_a_retention_period_and_aadhaar_must_be_sensitive():
    sensitive = [{"key": "id_proof", "label": "Government ID", "sensitive": True}]
    with pytest.raises(SettingsError, match="kept"):
        OnboardingConfig.model_validate(_paid_self_service(documents=sensitive))
    OnboardingConfig.model_validate(_paid_self_service(documents=sensitive, policies={"refund_policy": "x" * 5, "identity_document_retention_days": 365}))
    for doc in ({"key": "aadhaar", "label": "ID"}, {"key": "id_card", "label": "Aadhar card"}):
        with pytest.raises(SettingsError, match="sensitive"):
            OnboardingConfig.model_validate(_paid_self_service(documents=[doc]))
