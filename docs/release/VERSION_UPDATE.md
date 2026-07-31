# VERSION_UPDATE — bump 0.1.0 → 1.0.0

The repository is currently and **consistently** at version `0.1.0` (there is no
version *inconsistency* — every artifact agrees). Cutting v1.0.0 requires the
following one-line edits. These are release-labeling changes only; they do not
alter runtime behavior.

> Perform these as part of the release commit, immediately before tagging.
> Do **not** back-port unrelated changes into the release commit.

## Files to update

| File | Current | New | Notes |
|---|---|---|---|
| `apps/api/app/main.py` | `version="0.1.0"` (FastAPI app) | `version="1.0.0"` | Drives OpenAPI `info.version` / `/docs`, `/openapi.json` |
| `apps/web/package.json` | `"version": "0.1.0"` | `"version": "1.0.0"` | line 4 |
| `apps/student-portal/package.json` | `"version": "0.1.0"` | `"version": "1.0.0"` | line 4 |
| `apps/trainer-portal/package.json` | `"version": "0.1.0"` | `"version": "1.0.0"` | line 4 |
| `apps/corporate-portal/package.json` | `"version": "0.1.0"` | `"version": "1.0.0"` | line 4 |

## Suggested procedure

```bash
# From the repository root, on a release branch cut from 925bfa0.
# Backend (FastAPI app version):
#   edit apps/api/app/main.py -> version="1.0.0"

# Frontends:
for app in web student-portal trainer-portal corporate-portal; do
  # bump the "version" field to 1.0.0 (do not run npm version, which also tags)
  node -e "const f='apps/$app/package.json';const p=require('./'+f);p.version='1.0.0';require('fs').writeFileSync(f, JSON.stringify(p,null,2)+'\n')"
done
```

## Verification

```bash
grep -REn '"version"\s*:\s*"1.0.0"' apps/*/package.json   # 4 matches
grep -n 'version="1.0.0"' apps/api/app/main.py            # 1 match
# Optional: start the API and confirm /openapi.json reports info.version == "1.0.0"
```

## Commit

```bash
git add apps/api/app/main.py apps/web/package.json apps/student-portal/package.json \
        apps/trainer-portal/package.json apps/corporate-portal/package.json \
        CHANGELOG.md RELEASE_NOTES.md
git commit -m "chore(release): ERPX v1.0.0"
```

Then follow `docs/release/GIT_TAG_INSTRUCTIONS.md`.
