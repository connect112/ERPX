#!/usr/bin/env bash
# Rolling-deploys ERPX to Kubernetes: runs migrations as a one-off Job,
# then updates each Deployment's image tag and waits for the rollout to
# finish. Intended to run after .github/workflows/docker-publish.yml has
# pushed images tagged with the git SHA.
#
# Usage: ./deploy.sh <image-tag> [namespace]
set -euo pipefail

IMAGE_TAG="${1:?Usage: deploy.sh <image-tag> [namespace]}"
NAMESPACE="${2:-erpx}"
REGISTRY="${ERPX_REGISTRY:-ghcr.io/gir-technologies}"

echo "==> Deploying ERPX image tag '${IMAGE_TAG}' to namespace '${NAMESPACE}'"

echo "==> Running database migrations"
kubectl delete job erpx-migrate -n "${NAMESPACE}" --ignore-not-found
kubectl run erpx-migrate --restart=Never -n "${NAMESPACE}" \
  --image="${REGISTRY}/erpx-api:${IMAGE_TAG}" \
  --env-from=configmap/erpx-config --env-from=secret/erpx-secrets \
  --command -- alembic upgrade head
kubectl wait --for=condition=Ready pod/erpx-migrate -n "${NAMESPACE}" --timeout=120s || true
kubectl logs erpx-migrate -n "${NAMESPACE}"
kubectl delete pod erpx-migrate -n "${NAMESPACE}" --ignore-not-found

echo "==> Rolling out erpx-api"
kubectl set image deployment/erpx-api api="${REGISTRY}/erpx-api:${IMAGE_TAG}" -n "${NAMESPACE}"
kubectl rollout status deployment/erpx-api -n "${NAMESPACE}" --timeout=300s

echo "==> Rolling out erpx-celery-worker"
kubectl set image deployment/erpx-celery-worker celery-worker="${REGISTRY}/erpx-api:${IMAGE_TAG}" -n "${NAMESPACE}"
kubectl rollout status deployment/erpx-celery-worker -n "${NAMESPACE}" --timeout=300s

echo "==> Rolling out erpx-celery-beat"
kubectl set image deployment/erpx-celery-beat celery-beat="${REGISTRY}/erpx-api:${IMAGE_TAG}" -n "${NAMESPACE}"
kubectl rollout status deployment/erpx-celery-beat -n "${NAMESPACE}" --timeout=180s

echo "==> Rolling out erpx-web"
kubectl set image deployment/erpx-web web="${REGISTRY}/erpx-web:${IMAGE_TAG}" -n "${NAMESPACE}"
kubectl rollout status deployment/erpx-web -n "${NAMESPACE}" --timeout=180s

echo "==> Deployment complete."
