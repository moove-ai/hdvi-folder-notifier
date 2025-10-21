# Cloud Build Triggers

This document explains how Cloud Build is triggered for the HDVI Folder Notifier service.

## Current Setup

### Manual Trigger (Always Available)
```bash
gcloud builds submit --project=moove-build --config=cloudbuild.yaml .
```
This runs `gcloud builds submit` directly, useful for:
- Testing changes before pushing to GitHub
- Emergency deployments
- One-off builds

### Automatic Triggers (Optional)

#### GitHub Push Trigger
- **When**: Every push to `main` branch
- **What**: Builds Docker image + deploys via Cloud Deploy
- **Where**: `moove-build` project
- **Files**: All files except `README.md`, `*.md`, `terraform/**`

#### GitHub PR Trigger  
- **When**: Pull requests targeting `main` branch
- **What**: Builds Docker image + deploys via Cloud Deploy
- **Where**: `moove-build` project
- **Comments**: Enabled (can trigger builds via comments)

## Configuration

### Enable/Disable Triggers
Edit `terraform/terraform.tfvars`:
```hcl
# Enable automatic GitHub triggers
enable_github_triggers = true

# GitHub repository details
github_owner = "moove-ai"
github_repo = "hdvi-folder-notifier"
```

### Deploy Triggers
```bash
cd terraform
terraform apply
```

### View Active Triggers
```bash
gcloud builds triggers list --project=moove-build --filter="name~hdvi-folder-notifier"
```

## Trigger Details

### Push Trigger
- **Name**: `hdvi-folder-notifier-github`
- **Branch**: `^main$` (exact match)
- **Service Account**: `deployer@moove-build.iam.gserviceaccount.com`
- **Build File**: `cloudbuild.yaml`
- **Substitutions**: `_SERVICE_NAME=hdvi-folder-notifier`

### PR Trigger
- **Name**: `hdvi-folder-notifier-pr`
- **Branch**: `^main$` (PRs targeting main)
- **Comment Control**: `COMMENTS_ENABLED`
- **Service Account**: `deployer@moove-build.iam.gserviceaccount.com`
- **Build File**: `cloudbuild.yaml`
- **Substitutions**: `_SERVICE_NAME=hdvi-folder-notifier`

## Workflow

### Development Workflow
1. **Local Development**: Make changes locally
2. **Test Build**: `gcloud builds submit --project=moove-build --config=cloudbuild.yaml .` (manual)
3. **Create PR**: Push to feature branch, create PR
4. **PR Build**: Automatic build on PR creation/update
5. **Merge**: Merge to `main`
6. **Production Deploy**: Automatic build + deploy on push to `main`

### Emergency Workflow
1. **Hotfix**: Make changes directly on `main` or create hotfix branch
2. **Manual Deploy**: `gcloud builds submit --project=moove-build --config=cloudbuild.yaml .` (bypasses GitHub)
3. **Monitor**: Check Cloud Deploy progress

## Monitoring

### View Build History
```bash
# All builds
gcloud builds list --project=moove-build --filter="trigger.name~hdvi-folder-notifier"

# Recent builds
gcloud builds list --project=moove-build --filter="trigger.name~hdvi-folder-notifier" --limit=10
```

### View Specific Build
```bash
gcloud builds describe BUILD_ID --project=moove-build
```

### View Build Logs
```bash
gcloud builds log BUILD_ID --project=moove-build
```

## Troubleshooting

### Trigger Not Firing
1. Check GitHub webhook is installed
2. Verify repository permissions
3. Check trigger is enabled: `gcloud builds triggers describe TRIGGER_NAME --project=moove-build`

### Build Failing
1. Check build logs: `gcloud builds log BUILD_ID --project=moove-build`
2. Verify service account permissions
3. Check Cloud Deploy pipeline status

### Permission Issues
Ensure the `deployer@moove-build.iam.gserviceaccount.com` has:
- `Cloud Build Editor` role
- `Cloud Deploy Admin` role  
- `Artifact Registry Writer` role
- `Cloud Run Admin` role (for target project)

## Security

- Triggers use service account authentication
- No personal access tokens required
- GitHub webhook uses GCP's built-in integration
- All builds run in isolated Cloud Build environment
