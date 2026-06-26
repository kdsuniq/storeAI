#!/usr/bin/env bash
set -euo pipefail

# Deploy Store with AI to Yandex Managed Kubernetes
# Usage:
#   export REGISTRY_ID=crpXXXXXXXX
#   export FRONTEND_URL=https://your-domain.ru
#   ./deploy.sh

ROOT="$(cd "$(dirname "$0")" && pwd)"
REGISTRY_ID="${REGISTRY_ID:-<REGISTRY_ID>}"
NAMESPACE="store-ai"

echo "==> Building Docker images"
docker build -f "${ROOT}/backend/Dockerfile" -t "cr.yandex/${REGISTRY_ID}/store-ai-backend:latest" "${ROOT}"
docker build -f "${ROOT}/frontend/Dockerfile" -t "cr.yandex/${REGISTRY_ID}/store-ai-frontend:latest" "${ROOT}"

echo "==> Pushing to Yandex Container Registry"
docker push "cr.yandex/${REGISTRY_ID}/store-ai-backend:latest"
docker push "cr.yandex/${REGISTRY_ID}/store-ai-frontend:latest"

echo "==> Applying Kubernetes manifests"
kubectl apply -f "${ROOT}/k8s/namespace.yaml"
kubectl apply -f "${ROOT}/k8s/configmap.yaml"
if [ -f "${ROOT}/k8s/secret.yaml" ]; then
  kubectl apply -f "${ROOT}/k8s/secret.yaml"
else
  echo "WARNING: k8s/secret.yaml not found. Copy secret.example.yaml -> secret.yaml and fill values."
fi
kubectl apply -f "${ROOT}/k8s/postgres.yaml"
kubectl -n "${NAMESPACE}" wait --for=condition=available deploy/postgres --timeout=180s

echo "==> Running migrations"
kubectl -n "${NAMESPACE}" delete job/backend-migrate --ignore-not-found
sed "s|<REGISTRY_ID>|${REGISTRY_ID}|g" "${ROOT}/k8s/migrate-job.yaml" | kubectl apply -f -
kubectl wait --for=condition=complete job/backend-migrate -n "${NAMESPACE}" --timeout=180s

echo "==> Applying application workloads"
sed "s|<REGISTRY_ID>|${REGISTRY_ID}|g" "${ROOT}/k8s/backend.yaml" | kubectl apply -f -
sed "s|<REGISTRY_ID>|${REGISTRY_ID}|g" "${ROOT}/k8s/frontend.yaml" | kubectl apply -f -

echo "==> Done. Get external IP:"
kubectl get svc frontend -n "${NAMESPACE}"

echo ""
echo "Create admin user:"
echo "kubectl exec -it deploy/backend -n ${NAMESPACE} -- python manage.py createsuperuser"
