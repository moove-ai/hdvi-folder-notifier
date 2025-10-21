# Cloud Deploy Architecture

## Overview

The HDVI Folder Notifier uses **Cloud Deploy** for service deployment, following the same pattern as moove-webservice. This separates service deployment from infrastructure management.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Git Repo                                                     │
│  ├── service/production.yaml  (Cloud Run config)             │
│  ├── clouddeploy.yaml         (Delivery pipeline)            │
│  ├── skaffold.yaml            (Deploy config)                │
│  ├── cloudbuild.yaml          (Build + deploy trigger)       │
│  └── terraform/               (Infrastructure)               │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Cloud Build (moove-build)                                    │
│  1. Build Docker image                                        │
│  2. Push to Artifact Registry                                 │
│  3. Trigger Cloud Deploy                                      │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Cloud Deploy (moove-build)                                   │
│  1. Render service manifest                                   │
│  2. Deploy to Cloud Run                                       │
│  3. Send Slack notification                                   │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Cloud Run (moove-data-pipelines/us-central1)                │
│  - Service: hdvi-folder-notifier                             │
│  - Image: us-docker.pkg.dev/moove-build/...                  │
└──────────────────────────────────────────────────────────────┘
```

## Why Cloud Deploy?

### Benefits

1. **Standard Pipeline**: Consistent with moove-webservice, moove-process-service
2. **Deployment History**: Track all deployments, rollbacks
3. **Progressive Delivery**: Support for canary/blue-green (future)
4. **Separation**: Service config separate from infrastructure
5. **Rollbacks**: Easy to rollback to previous version

### vs Direct Terraform

| Aspect | Cloud Deploy | Terraform |
|--------|--------------|-----------|
| **Service Updates** | Fast (< 2 min) | Slower (Terraform plan/apply) |
| **Rollback** | Built-in | Manual state manipulation |
| **History** | Full deployment log | Terraform state only |
| **Config Location** | `service/*.yaml` | `terraform/main.tf` |
| **Consistency** | Matches other services | Different pattern |

## File Structure

```
hdvi-folder-notifier/
├── service/
│   └── production.yaml           # Cloud Run service manifest
├── clouddeploy.yaml               # Delivery pipeline definition
├── skaffold.yaml                  # Deploy configuration
├── cloudbuild.yaml                # Build + deploy trigger
└── terraform/                     # Infrastructure only
    ├── main.tf                    # Pub/Sub, Firestore, IAM
    └── ...
```

## Key Files

### `service/production.yaml`

Knative Cloud Run service manifest:
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hdvi-folder-notifier
spec:
  template:
    spec:
      containers:
      - image: app  # Replaced by Cloud Deploy
        env:
        - name: GCP_PROJECT
          value: moove-data-pipelines
        ...
```

### `clouddeploy.yaml`

Defines deployment pipeline:
```yaml
apiVersion: deploy.cloud.google.com/v1
kind: DeliveryPipeline
metadata:
  name: hdvi-folder-notifier
serialPipeline:
  stages:
    - targetId: production
      ...
---
kind: Target
metadata:
  name: production-us-central1
run:
  location: projects/moove-data-pipelines/locations/us-central1
```

### `skaffold.yaml`

Tells Cloud Deploy how to deploy:
```yaml
apiVersion: skaffold/v4beta7
kind: Config
profiles:
  - name: production
    manifests:
      rawYaml:
        - service/production.yaml
```

### `cloudbuild.yaml`

Triggers build and deployment:
```yaml
steps:
  - id: build
    name: gcr.io/cloud-builders/docker
    ...
  
  - id: deploy
    name: gcr.io/google.com/cloudsdktool/cloud-sdk
    script: |
      gcloud deploy releases create ...
```

## Deployment Flow

### 1. Developer Pushes Code

```bash
git push origin main
# Or manually: gcloud builds submit --project=moove-build --config=cloudbuild.yaml
```

### 2. Cloud Build Runs

- Builds Docker image
- Tags with `:SHORT_SHA` and `:latest`
- Pushes to Artifact Registry
- Applies Cloud Deploy pipeline
- Creates Cloud Deploy release

### 3. Cloud Deploy Deploys

- Renders `service/production.yaml`
- Replaces `image: app` with actual image
- Deploys to Cloud Run
- Runs post-deploy actions (Slack notification)

### 4. Service is Live

- Cloud Run service updated
- Pub/Sub continues to work (no downtime)
- Slack notification sent

## Configuration Changes

### To Change Service Config

Edit `service/production.yaml`:
```yaml
resources:
  limits:
    cpu: '2'      # Changed from 1
    memory: 1Gi   # Changed from 512Mi
```

Deploy:
```bash
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

### To Change Infrastructure

Edit `terraform/main.tf` or `terraform/terraform.tfvars`:
```hcl
bucket_name = "new-bucket"
```

Deploy:
```bash
cd terraform && terraform init && terraform apply
```

## Monitoring Deployments

### Via Console

https://console.cloud.google.com/deploy/delivery-pipelines/us-central1/hdvi-folder-notifier?project=moove-build

### Via CLI

```bash
# List recent releases
gcloud deploy releases list \
  --delivery-pipeline=hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-build

# Get release details
gcloud deploy releases describe RELEASE_NAME \
  --delivery-pipeline=hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-build

# List rollouts
gcloud deploy rollouts list \
  --delivery-pipeline=hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-build
```

## Rollback

### Via Console

1. Go to Cloud Deploy pipeline
2. Find previous release
3. Click "Rollback"

### Via CLI

```bash
gcloud deploy releases rollback RELEASE_NAME \
  --delivery-pipeline=hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-build \
  --to-target=production-us-central1
```

## Troubleshooting

### Deployment Stuck

```bash
# Check rollout status
gcloud deploy rollouts describe ROLLOUT_NAME \
  --delivery-pipeline=hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-build

# Check Cloud Run service
gcloud run services describe hdvi-folder-notifier \
  --region=us-central1 \
  --project=moove-data-pipelines
```

### Service Won't Start

Check Cloud Run logs:
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=hdvi-folder-notifier" \
  --project=moove-data-pipelines \
  --limit=50
```

Common issues:
- Secret not set (add Slack webhook)
- Firestore not created (run Terraform)
- Image pull failed (check Artifact Registry permissions)

### Can't Find Deployment Pipeline

```bash
# Ensure pipeline is created
gcloud deploy apply \
  --file=clouddeploy.yaml \
  --region=us-central1 \
  --project=moove-build
```

## Multi-Environment Support (Future)

To add staging environment:

1. Create `service/staging.yaml`
2. Update `clouddeploy.yaml` with staging target
3. Update `skaffold.yaml` with staging profile
4. Deploy infrastructure to staging project

## Integration with CI/CD

### GitHub Actions

```yaml
- name: Deploy
  run: |
    gcloud builds submit \
      --project=moove-build \
      --config=cloudbuild.yaml
```

### Cloud Build Trigger

Create trigger in moove-build:
```bash
gcloud builds triggers create github \
  --repo-name=hdvi-folder-notifier \
  --repo-owner=YOUR_ORG \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --project=moove-build
```

## Best Practices

1. **Always test locally first** with Docker
2. **Review service manifest** before deploying
3. **Use specific image tags** for production (`:SHORT_SHA`, not `:latest`)
4. **Monitor rollouts** in Cloud Deploy console
5. **Keep service config simple** - complexity in code, not config
6. **Document env vars** in code comments
7. **Use consistent patterns** across all services

## Comparison with moove-webservice

| Aspect | moove-webservice | hdvi-folder-notifier |
|--------|------------------|---------------------|
| Platform | GKE (Kubernetes) | Cloud Run |
| Config Location | `kustomize/` | `service/` |
| Manifests | Deployment, Service, Ingress | Service only |
| Complexity | High (K8s resources) | Low (single file) |
| Scaling | HPA, KEDA | Native Cloud Run |
| Cost | Always running | Scales to zero |

## Summary

Cloud Deploy provides a production-grade deployment pipeline while keeping the service simple. Infrastructure management (Terraform) is separate, allowing independent updates to service and infrastructure.

This pattern matches moove-webservice and provides a consistent deployment experience across all services.

