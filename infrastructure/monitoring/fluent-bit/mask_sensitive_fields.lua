-- Fluent Bit Lua filter: pipeline-level defense-in-depth for sensitive
-- fields, applied to every JSON log record before it reaches Loki.
--
-- This does NOT replace the application-level checklist item in
-- docs/deployment/production-checklist.md ("verify app/core/logging_config.py
-- doesn't log full request bodies for /auth/* endpoints") — that must
-- still be true, since this filter only catches values under known
-- sensitive key *names*, not every possible way a secret could end up in
-- a log line's free-text message. This is a second, independent layer:
-- if a future log call anywhere in the codebase ever accidentally
-- includes a field named "password" or "token", it gets redacted here
-- before being durably stored in Loki, rather than relying solely on
-- code review to catch it at the source every time.
--
-- Walks the record recursively so nested objects (e.g. AuditLog-style
-- "changes" diffs, or any dict passed as a structlog kwarg) are covered,
-- not just top-level keys.

local SENSITIVE_KEYS = {
    password = true,
    old_password = true,
    new_password = true,
    password_hash = true,
    token = true,
    access_token = true,
    refresh_token = true,
    secret = true,
    client_secret = true,
    api_key = true,
    authorization = true,
    otp = true,
    otp_code = true,
    two_factor_secret = true,
    credit_card = true,
    card_number = true,
    cvv = true,
    ssn = true,
}

local REDACTED = "***REDACTED***"

local function mask_value(key, value)
    if type(key) == "string" and SENSITIVE_KEYS[string.lower(key)] then
        return REDACTED
    end
    return value
end

local function walk(tbl)
    for key, value in pairs(tbl) do
        if type(value) == "table" then
            walk(value)
        else
            tbl[key] = mask_value(key, value)
        end
    end
end

function mask_sensitive_fields(tag, timestamp, record)
    walk(record)
    return 1, timestamp, record
end
