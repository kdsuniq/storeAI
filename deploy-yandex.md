# Deploy to Yandex Cloud Managed Kubernetes

## 1. Login and select folder

```bash
yc init
yc config list
```

Do not commit service account keys or real secrets.

## 2. Create a Container Registry

```bash
yc container registry create --name store-ai
yc container registry list
```

Copy the registry ID and export it:

```bash
export REGISTRY_ID=<registry_id>
```

## 3. Build and push images

```bash
docker build -f backend/Dockerfile -t cr.yandex/$REGISTRY_ID/store-ai-backend:latest .
docker build -f frontend/Dockerfile -t cr.yandex/$REGISTRY_ID/store-ai-frontend:latest .

yc container registry configure-docker
docker push cr.yandex/$REGISTRY_ID/store-ai-backend:latest
docker push cr.yandex/$REGISTRY_ID/store-ai-frontend:latest
```

## 4. Prepare Kubernetes manifests

`deploy.sh` substitutes `<REGISTRY_ID>` while applying the app manifests. If you apply YAML manually, replace `<REGISTRY_ID>` in `k8s/backend.yaml`, `k8s/frontend.yaml`, and `k8s/migrate-job.yaml`.

Create a real secret file from the example, but do not commit it:

```bash
cp k8s/secret.example.yaml k8s/secret.yaml
```

Edit:

```yaml
DJANGO_SECRET_KEY: ...
POSTGRES_PASSWORD: ...
OPENROUTER_API_KEY: ...
```

## 5. Connect kubectl to the cluster

If the cluster already exists:

```bash
yc managed-kubernetes cluster get-credentials <cluster_name_or_id> --external
kubectl get nodes
```

If there is no cluster yet, create it in the Yandex Cloud console or with `yc managed-kubernetes`.

## 6. Deploy

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/postgres.yaml
kubectl -n store-ai wait --for=condition=available deploy/postgres --timeout=180s
sed "s|<REGISTRY_ID>|$REGISTRY_ID|g" k8s/migrate-job.yaml | kubectl apply -f -
kubectl -n store-ai wait --for=condition=complete job/backend-migrate --timeout=120s
sed "s|<REGISTRY_ID>|$REGISTRY_ID|g" k8s/backend.yaml | kubectl apply -f -
sed "s|<REGISTRY_ID>|$REGISTRY_ID|g" k8s/frontend.yaml | kubectl apply -f -
```

Get external IP:

```bash
kubectl -n store-ai get svc frontend
```

## Notes

- For production, prefer Managed Service for PostgreSQL instead of the in-cluster `postgres.yaml`.
- The frontend calls `/api`, and nginx proxies it to the backend service.
- Product images are stored on the `backend-media` PVC. For several backend replicas, move media to object storage first.
- The backend image uses Python 3.11 because the local Python 3.14 venv caused slow Django startup.
