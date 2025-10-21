# Terraform Deployment Guide

Complete guide for deploying HDVI Folder Notifier with Terraform.

## Quick Start

```bash
# One command deploys everything
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```

This builds the container and deploys all infrastructure.

## Step-by-Step Deployment

### 1. Build Container Image

Build in the `moove-build` project (where all builds happen):

```bash
gcloud builds submit \
  --project=moove-build \
  --config=cloudbuild.yaml
```

This pushes to: `us-docker.pkg.dev/moove-build/docker-us/hdvi-folder-notifier`

### 2. Configure Slack Webhook

**Option A: Via Terraform variable**

Create `terraform/terraform.tfvars.secret`:
```hcl
slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

Then pass it to Terraform:
```bash
cd terraform
terraform apply -var-file="terraform.tfvars" -var-file="terraform.tfvars.secret"
```

**Option B: Manage secret manually (recommended)**

Leave `slack_webhook_url` empty in `terraform.tfvars`, then after applying:
```bash
echo -n "YOUR_WEBHOOK_URL" | gcloud secrets versions add hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=-
```

### 3. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

## What Gets Created

1. **Secret Manager Secret**: `hdvi-folder-notifier-slack-webhook`
2. **Cloud Run Service**: `hdvi-folder-notifier` (with health checks, auto-scaling)
3. **Service Account**: `hdvi-folder-notifier-invoker` (for Pub/Sub)
4. **Pub/Sub Subscription**: `hdvi-folder-notifier-sub` (push to Cloud Run)
5. **IAM Bindings**: 
   - Cloud Run Invoker for Pub/Sub SA
   - Firestore User for Cloud Run SA
   - Secret Accessor for Cloud Run SA

## Configuration Options

Edit `terraform/terraform.tfvars`:

```hcl
# Update container image after building
container_image = "gcr.io/moove-data-pipelines/hdvi-folder-notifier:v1.0.0"

# Adjust Cloud Run resources
memory        = "1Gi"    # Increase if needed
cpu           = "2"      # Increase if needed
min_instances = 1        # Set > 0 to keep warm
max_instances = 20       # Increase for high traffic

# Change service name
service_name = "hdvi-notifier-staging"
```

## Updating the Service

### Update Code Only

```bash
# Build new image with specific tag
gcloud builds submit --project=moove-build --config=cloudbuild.yaml

# Update terraform.tfvars with new tag if needed
container_image = "us-docker.pkg.dev/moove-build/docker-us/hdvi-folder-notifier:COMMIT_SHA"

# Apply
cd terraform
terraform apply
```

Note: Each build creates two tags: `:latest` and `:SHORT_SHA`

### Update Configuration

```bash
# Edit terraform.tfvars (e.g., increase memory)
cd terraform
terraform apply
```

## Managing Secrets

### View Current Secret

```bash
gcloud secrets versions access latest \
  --secret=hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines
```

### Update Secret

```bash
echo -n "NEW_WEBHOOK_URL" | gcloud secrets versions add hdvi-folder-notifier-slack-webhook \
  --project=moove-data-pipelines \
  --data-file=-
```

Cloud Run will automatically use the new version (configured to use "latest").

## State Management

### Local State (Default)

State stored in `terraform.tfstate` - **do not commit**.

### Remote State (Recommended)

Add to `main.tf`:

```hcl
terraform {
  backend "gcs" {
    bucket = "moove-terraform-state"
    prefix = "hdvi-folder-notifier"
  }
}
```

Then migrate:

```bash
terraform init -migrate-state
```

## Multi-Environment Setup

### Directory Structure

```
terraform/
  environments/
    dev/
      terraform.tfvars
    staging/
      terraform.tfvars
    production/
      terraform.tfvars
```

### Deploy to Different Environments

```bash
cd terraform
terraform workspace new staging
terraform apply -var-file="environments/staging/terraform.tfvars"
```

Or use different state files:

```bash
terraform apply -var-file="environments/staging/terraform.tfvars" -state="staging.tfstate"
```

## Rollback

### Rollback to Previous Image

```bash
# Update terraform.tfvars to previous image
container_image = "gcr.io/moove-data-pipelines/hdvi-folder-notifier:v1.0.0"

# Apply
cd terraform
terraform apply
```

### Full Rollback

```bash
cd terraform
terraform plan -destroy
terraform destroy  # WARNING: This deletes everything
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy HDVI Notifier

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Authenticate to GCP
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build image
        run: |
          gcloud builds submit --tag=gcr.io/moove-data-pipelines/hdvi-folder-notifier:${{ github.sha }}
      
      - name: Deploy with Terraform
        run: |
          cd terraform
          terraform init
          terraform apply -auto-approve \
            -var="container_image=gcr.io/moove-data-pipelines/hdvi-folder-notifier:${{ github.sha }}"
```

### Cloud Build Example

```yaml
# cloudbuild.yaml
steps:
  # Build image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/hdvi-folder-notifier:$COMMIT_SHA', '.']
  
  # Push image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/hdvi-folder-notifier:$COMMIT_SHA']
  
  # Deploy with Terraform
  - name: 'hashicorp/terraform:1.6'
    dir: 'terraform'
    args:
      - 'apply'
      - '-auto-approve'
      - '-var=container_image=gcr.io/$PROJECT_ID/hdvi-folder-notifier:$COMMIT_SHA'
```

## Troubleshooting

### Error: container_image variable required

Add to `terraform.tfvars`:
```hcl
container_image = "gcr.io/moove-data-pipelines/hdvi-folder-notifier:latest"
```

### Error: Secret version not found

The secret exists but has no version. Add one:
```bash
echo -n "YOUR_WEBHOOK" | gcloud secrets versions add hdvi-folder-notifier-slack-webhook --data-file=-
```

### Error: Cloud Run service unhealthy

Check logs:
```bash
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=hdvi-folder-notifier' \
  --project=moove-data-pipelines \
  --limit=50
```

Common issues:
- Secret not set (add webhook URL)
- Firestore not created (create manually)
- Image build failed (check Cloud Build logs)

## Validation

```bash
# Check Cloud Run service
gcloud run services describe hdvi-folder-notifier \
  --project=moove-data-pipelines \
  --region=us-central1

# Check Pub/Sub subscription
gcloud pubsub subscriptions describe hdvi-folder-notifier-sub \
  --project=moove-data-pipelines

# Test end-to-end
../test-notification.sh Prebind/2024/10/20
```

## Best Practices

1. **Use remote state** for team collaboration
2. **Tag images** with semantic versions (not just :latest)
3. **Manage secrets** outside Terraform (use gcloud or Secret Manager UI)
4. **Enable Cloud Run revisions** for easy rollback
5. **Use workspaces** or separate state files for multiple environments
6. **Review plans** before applying in production
7. **Automate** with CI/CD for consistency

## Cost Optimization

```hcl
# For low-traffic environments
min_instances = 0  # Scale to zero
memory        = "256Mi"  # Minimum needed
max_instances = 3   # Limit concurrency

# For high-traffic production
min_instances = 1   # Keep warm
memory        = "512Mi"
max_instances = 10
```

## Monitoring

Terraform outputs include URLs for monitoring:

```bash
cd terraform
terraform output cloud_run_service_url
```

Monitor in Cloud Console:
- Cloud Run: https://console.cloud.google.com/run
- Logs: https://console.cloud.google.com/logs
- Secrets: https://console.cloud.google.com/security/secret-manager

