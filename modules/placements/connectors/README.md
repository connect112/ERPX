# Job-board connectors

One module per source, each implementing the shared contract in `base.py`:

```python
async def fetch_postings(keywords: list[str], db: AsyncSession) -> ConnectorResult
```

This mirrors `packages/ai/client.py`'s pattern — the actual "one interface,
pluggable implementation" precedent already in this repo (`packages/storage`
turned out, on inspection, not to have that shape: it's a single concrete
client behind a cached singleton getter, not an interface with multiple
provider implementations). Here, instead of an `ABC` + subclasses, the
"interface" is a plain function signature every connector module implements
— consistent with connectors being simple, mostly-stateless HTTP callers
rather than long-lived objects.

## Adding a fifth source

1. Create `modules/placements/connectors/<source>.py` implementing
   `fetch_postings`.
2. Add one entry to `_CONNECTORS` in `__init__.py`.
3. If the source has real credentials, add them to `app/core/config.py` and
   `.env.example` following the existing block's style, defaulting to `""`.

Nothing else needs to change — `aggregation_service.py` iterates whatever
`fetch_all` returns.

## Current sources

| Source | Auth | Confirmed rate limit | Notes |
|---|---|---|---|
| Adzuna | `app_id`+`app_key` query params | 25/min, 250/day, 1000/week, 2500/month (Adzuna's own ToS) | Requires the "Jobs by Adzuna" branded attribution, not just a generic "via X" badge — see `adzuna_attribution.tsx` on both frontends. |
| Jooble | API key in URL path | **500-request lifetime cap**, not recurring (Jooble's own help-center docs) | Runs on its own weekly Celery beat entry, not the hourly one — see `jooble.py`'s module docstring. |
| Reed | HTTP Basic (key as username, blank password) | Not documented publicly; throttled defensively | |
| Arbeitnow | None required | Not documented publicly; throttled defensively | No keyword query param — filtered client-side plus the shared AI relevance filter. |

## Deliberately excluded

CyberSecJobs, InfoSec-Jobs.com, and ClearedJobs.net were researched and
excluded — none has a documented public API for individual job listings, so
none meets the task's own "only if it has a documented feed/API" bar. A
related site, infosecjobboard.com, does have a free JSON API, but it
publishes aggregate counts/benchmarks only, not raw postings — unsuitable
for populating individual `JobPosting` rows. Revisit if any of these
publishes a real listings API; adding one back is the same one-file +
one-registry-entry process above.
