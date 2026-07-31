# ERPX v1.0.0 — Git Release Tag Instructions

Tag the release **after** the version bump (`VERSION_UPDATE.md`) and a green CI
run. Use an **annotated, signed** tag so the release is auditable.

Release commit base: `925bfa0` (self-contained Docker image) or the
`chore(release): ERPX v1.0.0` commit on top of it.

## 1. Pre-tag checks

```bash
git status                      # clean working tree
git log --oneline -1            # expected release commit is HEAD
git tag --list 'v*'             # confirm v1.0.0 does not already exist
# CI green on this commit; migrations at head; smoke-test plan ready.
```

## 2. Create the annotated tag

```bash
git tag -a v1.0.0 -m "ERPX v1.0.0 — first production release" 
# Prefer a signed tag if signing keys are configured:
#   git tag -s v1.0.0 -m "ERPX v1.0.0 — first production release"
```

## 3. Verify

```bash
git tag -n99 v1.0.0             # shows the annotation
git rev-parse v1.0.0            # the commit it points to
git verify-tag v1.0.0          # only if signed
```

## 4. Push the tag

```bash
git push origin v1.0.0
```

Pushing the tag typically triggers the image publish workflow
(`docker-publish.yml`) which builds from the repo root and pushes
`ghcr.io/gir-technologies/erpx-api:latest` and `:<git-sha>`. Confirm the workflow
succeeds and the image is present in GHCR before deploying.

## 5. Create the GitHub Release

- Target the `v1.0.0` tag.
- Title: `ERPX v1.0.0`.
- Body: paste `RELEASE_NOTES.md` (link the full `CHANGELOG.md`).
- Attach any artifacts if applicable.

## Fixing a mistagged release (before wide distribution only)

```bash
git tag -d v1.0.0                       # delete local
git push origin :refs/tags/v1.0.0       # delete remote
# re-create on the correct commit, then push again
```

Do **not** move an already-distributed tag; cut `v1.0.1` instead.
