"""
Shared slowapi Limiter instance.

Defined in its own module (rather than inline in `app/main.py`, where it
originally lived) specifically so route modules can apply per-route
`@limiter.limit(...)` decorators without a circular import: `app/main.py`
imports every module's `routes.py` (via `app/api/v1/router.py`), so those
route modules cannot import the limiter back out of `app/main.py`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])
