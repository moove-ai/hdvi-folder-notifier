# Build Process

## Overview

The HDVI Folder Notifier follows the standard moove.ai build pattern:
- **Build Project**: `moove-build` (centralized builds)
- **Image Registry**: Artifact Registry (`us-docker.pkg.dev/moove-build/docker-us/`)
- **Deploy Project**: `moove-data-pipelines` (where the service runs)

## Build Architecture

```
Local Code
    ↓
Cloud Build (moove-build project)
    ↓
Artifact Registry (us-docker.pkg.dev/moove-build/docker-us/)
    ↓
Cloud Run (moove-data-pipelines project)
```

## Quick Build

```bash
gcloud builds submit \
  --project=moove-build \
  --config=cloudbuild.yaml
```

## Build Configuration

### cloudbuild.yaml

- Uses Docker with BuildKit for efficient caching
- Creates two tags per build:
  - `:latest` - always points to most recent
  - `:SHORT_SHA` - git commit SHA (e.g., `:a1b2c3d`)
- Logs stored in `moove-build-logs` bucket
- Build timeout: 20 minutes (1200s)
- 100GB disk for build cache

### Image Naming

```
us-docker.pkg.dev/moove-build/docker-us/hdvi-folder-notifier:latest
us-docker.pkg.dev/moove-build/docker-us/hdvi-folder-notifier:a1b2c3d
```

## Manual Build (for local testing)

```bash
# Build locally
docker build -t hdvi-folder-notifier:local .

# Test locally
docker run -p 8080:8080 \
  -e GCP_PROJECT=moove-data-pipelines \
  -e SLACK_WEBHOOK_URL=your-webhook \
  hdvi-folder-notifier:local
```

## Viewing Builds

### List recent builds

```bash
gcloud builds list \
  --project=moove-build \
  --filter="tags=hdvi-folder-notifier" \
  --limit=10
```

### View build logs

```bash
gcloud builds log BUILD_ID --project=moove-build
```

Or in Cloud Console:
https://console.cloud.google.com/cloud-build/builds?project=moove-build

### List images

```bash
gcloud artifacts docker images list \
  us-docker.pkg.dev/moove-build/docker-us/hdvi-folder-notifier \
  --project=moove-build
```

## CI/CD Integration

### Trigger builds from Git

Create a Cloud Build trigger in `moove-build`:

```bash
gcloud builds triggers create github \
  --project=moove-build \
  --repo-name=hdvi-folder-notifier \
  --repo-owner=YOUR_ORG \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

### Automatic deployment (optional)

Uncomment the Terraform steps in `cloudbuild.yaml` to auto-deploy after build.

## Build Permissions

The `deployer@moove-build.iam.gserviceaccount.com` service account needs:
- `roles/cloudbuild.builds.builder` in moove-build
- `roles/artifactregistry.writer` in moove-build
- `roles/run.admin` in moove-data-pipelines (for auto-deploy)

## Troubleshooting

### Build fails: permission denied

Ensure you have permission to submit builds:
```bash
gcloud projects add-iam-policy-binding moove-build \
  --member="user:YOUR_EMAIL" \
  --role="roles/cloudbuild.builds.editor"
```

### Can't pull image in Cloud Run

Ensure Cloud Run service account can pull from Artifact Registry:
```bash
gcloud artifacts repositories add-iam-policy-binding docker-us \
  --project=moove-build \
  --location=us \
  --member="serviceAccount:moove-data-pipelines@appspot.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
```

### Build is slow

- Docker BuildKit caching should make subsequent builds fast (~1-2 min)
- First build takes longer to populate cache
- Use `machineType: N1_HIGHCPU_8` for faster builds (already configured)
- 100GB disk helps with layer caching

## Best Practices

1. **Use :latest for development**, `:SHORT_SHA` for production
2. **Don't delete old images** - they're cheap to store and useful for rollback
3. **Tag releases** - Consider tagging major versions (v1.0.0)
4. **Monitor build costs** - Check Cloud Build dashboard monthly
5. **Keep Dockerfile lean** - Use multi-stage builds, minimize layers

## Cost

Typical monthly costs:
- Cloud Build: ~$1-5 (first 120 build-minutes free)
- Artifact Registry storage: ~$0.10/GB/month
- Build logs storage: Minimal

Total: < $10/month for typical usage

