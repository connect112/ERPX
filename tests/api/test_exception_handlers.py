"""
Regression tests for the global validation exception handler.

A ``RequestValidationError`` can carry non-JSON-serialisable values in each
error entry's ``input``/``ctx`` — most commonly the raw request body as
``bytes`` when a client posts a wrong content-type to a JSON endpoint.
``validation_exception_handler`` serialises ``exc.errors()`` into the error
envelope; before those errors were passed through ``jsonable_encoder``,
``json.dumps`` raised ``TypeError: Object of type bytes is not JSON
serializable`` and the fallback handler turned the clean 422 into a 500.

``test_bytes_in_validation_errors_serialise_cleanly`` pins the exact fix
deterministically (independent of the installed pydantic/FastAPI version, whose
per-error ``input`` shape for malformed JSON varies); the HTTP-level tests pin
the observable 422-not-500 behaviour end to end.
"""

import json

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from app.main import app

pytestmark = pytest.mark.api


async def test_bytes_in_validation_errors_serialise_cleanly():
    # A validation error whose `input` is raw bytes (the real-world trigger:
    # a wrong content-type body). Before the fix this crashed the handler's
    # json.dumps with "Object of type bytes is not JSON serializable".
    handler = app.exception_handlers[RequestValidationError]
    exc = RequestValidationError(
        [
            {
                "type": "json_invalid",
                "loc": ("body", 0),
                "msg": "JSON decode error",
                "input": b"email=admin@erpx.example.com&password=Admin@12345",
            }
        ]
    )
    request = Request({"type": "http", "method": "POST", "headers": [], "path": "/x"})

    response = await handler(request, exc)

    assert response.status_code == 422
    payload = json.loads(bytes(response.body))  # must not raise
    assert payload["success"] is False
    assert payload["error"]["code"] == "validation_error"
    # bytes was coerced to a string by jsonable_encoder rather than crashing.
    assert payload["error"]["details"][0]["input"] == "email=admin@erpx.example.com&password=Admin@12345"


async def test_wrong_content_type_body_returns_422_not_500(client):
    # Form-encoded body sent to a JSON endpoint: FastAPI fails to parse it as
    # JSON and routes through the validation handler. Must be a clean 422.
    resp = await client.post(
        "/api/v1/auth/login",
        content=b"email=admin@erpx.example.com&password=Admin@12345",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list) and body["error"]["details"]


async def test_missing_required_fields_returns_422(client):
    # Well-formed JSON but missing required fields flows through the same
    # handler and returns the same envelope shape.
    resp = await client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"] is not None
