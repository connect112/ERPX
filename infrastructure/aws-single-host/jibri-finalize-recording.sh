#!/usr/bin/env bash
# Jibri "finalize recording" script — runs on the dedicated recording
# instance once a recording session ends. Jibri invokes this with exactly
# one argument: the local directory the recording was written into (see
# https://github.com/jitsi/jibri's JibriServiceFinalizeCommandRunner).
#
# NOT YET TESTED END-TO-END — written ahead of provisioning the actual
# Jibri instance, since it needs no server to exist yet to write and
# review. Verify it for real once Jibri is live: run one real recording,
# confirm the S3 object appears and modules/live_classes/routes.py's
# POST /live-classes/recording-webhook actually attaches the URL.
#
# What it does:
#   1. Finds the recording file Jibri just wrote (named
#      "<room_name>_<timestamp>.<ext>" — see jibri's FileSink.kt).
#   2. Uploads it to S3.
#   3. Calls ERPX's recording webhook with the room name (which encodes
#      the live_class_id — see modules/live_classes/jitsi.py's
#      build_room_name/parse_live_class_id_from_room_name) and the
#      resulting URL, HMAC-signed the same way
#      modules/provisioning/dependencies.py's caller (Pentrix-share)
#      already signs its own webhook calls to ERPX.
#
# Configure via environment variables on the Jibri instance (e.g. in
# docker-jitsi-meet's .env, passed through to the jibri container):
#   JIBRI_S3_BUCKET          - e.g. pentrix-erpx-recordings
#   JIBRI_S3_PRESIGN_EXPIRY  - seconds the recording URL stays valid
#                              (default 604800 = 7 days; see the note
#                              below about a proper on-demand endpoint
#                              being the better long-term fix)
#   ERPX_API_BASE_URL        - e.g. https://erp.pentrix.in/api/v1
#   JIBRI_WEBHOOK_SECRET     - must match settings.JIBRI_WEBHOOK_SECRET
#                              on the ERPX side exactly
#
# NOTE on recording_url's lifetime: the bucket is private (no public
# objects), so this stores a presigned URL that expires. For a
# recording someone might want to watch well after 7 days, the correct
# fix is a small ERPX endpoint that mints a fresh presigned URL on
# demand when someone clicks "View Recording" — the same pattern
# modules/payroll already uses for payslip PDFs
# (apps/web/.../payslips-hooks.ts's useOpenPayslipPdf). Out of scope for
# this first pass; flagged here rather than silently left out.

set -euo pipefail

RECORDING_DIR="$1"
: "${JIBRI_S3_BUCKET:?JIBRI_S3_BUCKET must be set}"
: "${ERPX_API_BASE_URL:?ERPX_API_BASE_URL must be set}"
: "${JIBRI_WEBHOOK_SECRET:?JIBRI_WEBHOOK_SECRET must be set}"
JIBRI_S3_PRESIGN_EXPIRY="${JIBRI_S3_PRESIGN_EXPIRY:-604800}"

log() { echo "[jibri-finalize] $*" >&2; }

# Recording files are named "<room_name>_<timestamp>.<ext>" (see
# jibri's FileSink.kt) -- pick the actual media file, not any sidecar
# metadata Jibri also writes into the same directory.
recording_file=$(find "$RECORDING_DIR" -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.mkv" \) | head -n1)
if [[ -z "$recording_file" ]]; then
  log "No recording file found in $RECORDING_DIR — nothing to upload."
  exit 1
fi

filename=$(basename "$recording_file")
# Strip "_<timestamp>.<ext>" to recover the room name -- everything up
# to the last underscore-prefixed segment before the extension.
room_name=$(echo "$filename" | sed -E 's/_[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}\.[a-zA-Z0-9]+$//')

if [[ "$room_name" != erpx-* ]]; then
  log "Room name '$room_name' doesn't look like an ERPX room (expected erpx-<hex>) -- skipping upload/webhook."
  exit 0
fi

s3_key="recordings/${filename}"
log "Uploading $recording_file to s3://${JIBRI_S3_BUCKET}/${s3_key}"
aws s3 cp "$recording_file" "s3://${JIBRI_S3_BUCKET}/${s3_key}" --only-show-errors

recording_url=$(aws s3 presign "s3://${JIBRI_S3_BUCKET}/${s3_key}" --expires-in "$JIBRI_S3_PRESIGN_EXPIRY")

payload=$(printf '{"room_name":"%s","recording_url":"%s"}' "$room_name" "$recording_url")
timestamp=$(date +%s)
signed_payload="${timestamp}.${payload}"
signature=$(printf '%s' "$signed_payload" | openssl dgst -sha256 -hmac "$JIBRI_WEBHOOK_SECRET" | sed 's/^.* //')

log "Notifying ERPX for room $room_name"
http_status=$(curl -s -o /tmp/jibri-webhook-response.json -w '%{http_code}' \
  -X POST "${ERPX_API_BASE_URL}/live-classes/recording-webhook" \
  -H "Content-Type: application/json" \
  -H "X-Jibri-Timestamp: ${timestamp}" \
  -H "X-Jibri-Signature: ${signature}" \
  -d "$payload")

if [[ "$http_status" != "200" ]]; then
  log "ERPX webhook call failed (HTTP $http_status): $(cat /tmp/jibri-webhook-response.json)"
  exit 1
fi

log "Recording attached to live class for room $room_name."
