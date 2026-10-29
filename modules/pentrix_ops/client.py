"""
ERPX's signed calls to Pentrix's internal API (the other direction from student provisioning).

Every request is signed with the shared secret: HMAC-SHA256 over "<timestamp>.<METHOD>.<path and query>.<body>", the same construction
Pentrix verifies (backend/app/utils/erpx_auth.py). The signature covers the method and address, so it cannot be replayed against a
different endpoint. X-ERPX-Actor says which ERPX user the call is on behalf of, for Pentrix's audit trail.
"""
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError, ValidationError

_PREFIX = "/api/v1/internal/erpx"
DEFAULT_TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests put a fake Pentrix here
_TIMEOUT_SECONDS = 15


def sign(secret: str, timestamp: str, method: str, path_and_query: str, body: str) -> str:
    return hmac.new(secret.encode("utf-8"), f"{timestamp}.{method.upper()}.{path_and_query}.{body}".encode("utf-8"), hashlib.sha256).hexdigest()


class PentrixClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport or DEFAULT_TRANSPORT

    @staticmethod
    def configured() -> bool:
        return bool(settings.PENTRIX_INTERNAL_API_BASE_URL and settings.ERPX_INTERNAL_SERVICE_SECRET)

    async def request(self, method: str, path: str, body: dict | None = None, params: dict | None = None, actor: str | None = None) -> Any:
        if not self.configured():
            raise ServiceUnavailableError("The Pentrix connection is not configured (PENTRIX_INTERNAL_API_BASE_URL and ERPX_INTERNAL_SERVICE_SECRET).")
        query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        path_and_query = f"{_PREFIX}{path}" + (f"?{query}" if query else "")
        raw = json.dumps(body) if body is not None else ""
        timestamp = str(int(time.time()))
        headers = {
            "X-ERPX-Timestamp": timestamp,
            "X-ERPX-Signature": sign(settings.ERPX_INTERNAL_SERVICE_SECRET, timestamp, method, path_and_query, raw),
        }
        if actor:
            headers["X-ERPX-Actor"] = actor
        if raw:
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(base_url=settings.PENTRIX_INTERNAL_API_BASE_URL.rstrip("/"), timeout=_TIMEOUT_SECONDS, transport=self._transport) as http:
                response = await http.request(method, path_and_query, content=raw or None, headers=headers)
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError("Pentrix did not respond. Please try again in a moment.") from exc
        if response.status_code >= 400:
            self._raise(response)
        return response.json()

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        try:
            message = response.json().get("message") or response.text[:300]
        except ValueError:
            message = response.text[:300]
        message = message or "Pentrix refused that."
        if response.status_code == 404:
            raise NotFoundError("Pentrix booking", message)
        if response.status_code in (400, 422):
            raise ValidationError(message)
        if response.status_code in (403, 409):
            raise ConflictError(message)
        raise ServiceUnavailableError("Pentrix could not do that right now. Please try again.")

    # ------------------------------------------------------------------ the calls

    async def changes(self, cursor: str | None, limit: int = 200) -> dict:
        return await self.request("GET", "/bookings", params={"cursor": cursor, "limit": limit})

    async def booking(self, booking_id: str) -> dict:
        return await self.request("GET", f"/bookings/{booking_id}")

    async def assign(self, booking_id: str, staff_ref: str | None, staff_name: str | None, actor: str | None) -> dict:
        return await self.request("POST", f"/bookings/{booking_id}/assign", {"staff_ref": staff_ref, "staff_name": staff_name}, actor=actor)

    async def set_status(self, booking_id: str, status: str, actor: str | None) -> dict:
        return await self.request("POST", f"/bookings/{booking_id}/status", {"status": status}, actor=actor)

    async def reschedule(self, booking_id: str, slot_start: str, actor: str | None) -> dict:
        return await self.request("POST", f"/bookings/{booking_id}/reschedule", {"slot_start": slot_start}, actor=actor)

    async def cancel(self, booking_id: str, actor: str | None) -> dict:
        return await self.request("POST", f"/bookings/{booking_id}/cancel", {}, actor=actor)

    async def meeting(self, booking_id: str, url: str | None, actor: str | None) -> dict:
        return await self.request("POST", f"/bookings/{booking_id}/meeting", {"meeting_url": url}, actor=actor)

    async def notes(self, booking_id: str, notes: str | None, actor: str | None) -> dict:
        return await self.request("POST", f"/bookings/{booking_id}/notes", {"notes": notes}, actor=actor)

    async def availability(self, days: int | None = None) -> dict:
        return await self.request("GET", "/availability", params={"days": days})

    async def get_settings(self) -> dict:
        return await self.request("GET", "/booking-settings")

    async def put_settings(self, changes: dict, actor: str | None) -> dict:
        return await self.request("PUT", "/booking-settings", changes, actor=actor)

    async def blocks(self) -> list[dict]:
        return await self.request("GET", "/booking-blocks")

    async def add_block(self, start_at: str, end_at: str, reason: str, actor: str | None) -> dict:
        return await self.request("POST", "/booking-blocks", {"start_at": start_at, "end_at": end_at, "reason": reason}, actor=actor)

    async def delete_block(self, block_id: str, actor: str | None) -> dict:
        return await self.request("DELETE", f"/booking-blocks/{block_id}", actor=actor)
