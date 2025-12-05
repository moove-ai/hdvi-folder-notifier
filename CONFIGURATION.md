# Configuration Guide

## Environment Variables

All configuration is managed via Terraform and passed as environment variables to the Cloud Run service.

### Required Configuration

| Variable | Source | Purpose | Example |
|----------|--------|---------|---------|
| `GCP_PROJECT` | Terraform | GCP project for Firestore | `moove-data-pipelines` |
| `SLACK_WEBHOOK_URL` | Secret Manager | Slack notification endpoint | `https://hooks.slack.com/...` |

### Optional Configuration

| Variable | Default | Purpose | Example |
|----------|---------|---------|---------|
| `BUCKET_NAME` | `moove-incoming-data-u7x4ty` | GCS bucket to monitor | `your-bucket-name` |
| `MONITORED_PREFIXES` | `Prebind/,Postbind/,test/` | Folder prefixes to monitor | `Folder1/,Folder2/` |
| `ANALYTICS_BUCKET` | _(empty)_ | Optional bucket for CSV analytics log | `moove-incoming-hdvi-folder-tracking` |
| `ANALYTICS_OBJECT` | _(empty)_ | Object path for analytics CSV | `analytics/hdvi-folder-completions.csv` |
| `BIGQUERY_PROJECT_ID` | `GCP_PROJECT` | Project hosting the BigQuery dataset | `moove-data-pipelines` |
| `BIGQUERY_DATASET_ID` | _(empty)_ | Dataset that stores completion stats | `hdvi_folder_tracking` |
| `BIGQUERY_TABLE_ID` | _(empty)_ | Table name for completion stats | `folder_completions` |
| `DISABLE_COMPLETION_THREAD` | `false` | Skip periodic Firestore polling (set `true` for batch jobs) | `true` |
| `BACKFILL_START_DATE` | _(empty)_ | Default ISO timestamp for manual BigQuery backfill jobs | `2025-11-09T00:00:00Z` |
| `BACKFILL_END_DATE` | _(empty)_ | Optional exclusive end timestamp for backfill jobs | `2025-11-15T00:00:00Z` |

## Customizing Configuration

### Via Terraform

Edit `terraform/terraform.tfvars`:

```hcl
# Change the bucket to monitor
bucket_name = "different-bucket-name"

# Change monitored folders (comma-separated, include trailing slashes)
monitored_prefixes = "InputData/,ProcessedData/,TestData/"
```

Then apply:
```bash
cd terraform
terraform apply
```

### Via Environment Variables (Manual)

If deploying outside Terraform, set environment variables:

```bash
export GCP_PROJECT="moove-data-pipelines"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export BUCKET_NAME="your-bucket"
export MONITORED_PREFIXES="Folder1/,Folder2/,Folder3/"
```

## Configuration Examples

### Example 1: Different Bucket

Monitor a different GCS bucket:

```hcl
# terraform/terraform.tfvars
bucket_name = "my-other-bucket"
monitored_prefixes = "incoming/,staging/"
```

### Example 2: Single Folder

Monitor only one folder:

```hcl
# terraform/terraform.tfvars
monitored_prefixes = "production/"
```

### Example 3: Development Environment

Separate dev/prod configurations:

```hcl
# terraform/environments/dev.tfvars
project_id         = "moove-dev"
environment        = "development"
bucket_name        = "moove-dev-data"
monitored_prefixes = "test/,dev/"

# terraform/environments/prod.tfvars
project_id         = "moove-data-pipelines"
environment        = "production"
bucket_name        = "moove-incoming-data-u7x4ty"
monitored_prefixes = "Prebind/,Postbind/"
```

Deploy:
```bash
terraform apply -var-file="environments/dev.tfvars"
```

## Prefix Matching Rules

### How Prefixes Work

- Prefixes must match the **start** of the file path
- Include trailing slashes to match folders
- Case-sensitive matching

### Examples

**Configuration**: `monitored_prefixes = "Prebind/,test/"`

| File Path | Monitored? | Reason |
|-----------|------------|--------|
| `Prebind/2024/10/file.csv` | ✅ Yes | Starts with `Prebind/` |
| `test/validation.csv` | ✅ Yes | Starts with `test/` |
| `Postbind/data.csv` | ❌ No | Not in prefixes list |
| `archive/Prebind/file.csv` | ❌ No | Doesn't start with `Prebind/` |
| `prebind/file.csv` | ❌ No | Case mismatch |

### Best Practices

1. **Always use trailing slashes** for folder prefixes
2. **Be specific** - `data/incoming/` vs `data/`
3. **Test with actual paths** from your bucket
4. **Use consistent casing** - match your bucket structure exactly

## Changing Configuration

### Update Monitored Folders

```bash
# Edit terraform.tfvars
vim terraform/terraform.tfvars

# Change this line:
monitored_prefixes = "NewFolder1/,NewFolder2/"

# Apply changes
cd terraform
terraform apply
```

Cloud Run will automatically restart with the new configuration.

### Update Bucket

```bash
# Edit terraform.tfvars
vim terraform/terraform.tfvars

# Change this line:
bucket_name = "new-bucket-name"

# Apply changes
cd terraform
terraform apply
```

**Note**: You'll also need to update the Pub/Sub topic to publish events from the new bucket.

## Validation

### Check Current Configuration

View outputs after deployment:
```bash
cd terraform
terraform output
```

### Test with Sample File

```bash
# Send test notification
./test-notification.sh Prebind/2024/10/20
```

### View Logs

```bash
# Check what paths are being processed
./view-logs.sh 50 | grep "Processing file"
```

You should see:
```
Processing file: moove-incoming-data-u7x4ty/Prebind/2024/10/20/file.csv
```

## Troubleshooting

### Not receiving notifications

1. Check configured prefixes match your file paths:
   ```bash
   terraform output monitored_prefixes
   ```

2. Verify bucket name is correct:
   ```bash
   terraform output bucket_name
   ```

3. Check logs for "not in monitored path" messages:
   ```bash
   ./view-logs.sh | grep "not in monitored path"
   ```

### Case sensitivity issues

File paths are case-sensitive. Ensure your prefixes match exactly:
- ✅ `Prebind/` (correct)
- ❌ `prebind/` (won't match)
- ❌ `PREBIND/` (won't match)

### Prefix doesn't match

Add more specific prefixes or adjust to match your folder structure:
```hcl
# Too broad
monitored_prefixes = "data/"

# More specific
monitored_prefixes = "data/incoming/,data/staging/"
```

## Advanced Configuration

### Multiple Environments

Use Terraform workspaces:

```bash
# Create workspace
terraform workspace new staging

# Deploy with different config
terraform apply -var-file="staging.tfvars"
```

### Dynamic Prefixes

For advanced use cases, you could modify the code to:
- Read prefixes from Firestore
- Use regex patterns
- Load from external config file

This would require changes to `main.py`.

## Security Notes

- Bucket name and prefixes are **not sensitive** (can be in version control)
- Only the Slack webhook is sensitive (stored in Secret Manager)
- Configuration changes require Cloud Run redeployment
- Service account needs read access to the specified bucket

## Manual BigQuery Backfill Job

- Script entrypoint: `backfill_bigquery.py`
- Cloud Run Job manifest: `jobs/hdvi-folder-backfill.yaml`
- Default purpose: backfill folder completion stats starting 2025-11-09 into BigQuery

### Deploy the Job

```bash
gcloud run jobs replace jobs/hdvi-folder-backfill.yaml \
  --project moove-data-pipelines \
  --region us-central1
```

### Execute the Job

Override the window per run (CLI flags beat env vars):

```bash
gcloud run jobs execute hdvi-folder-backfill \
  --project moove-data-pipelines \
  --region us-central1 \
  --args="--start-date=2025-11-09T00:00:00Z","--end-date=2025-11-16T00:00:00Z"
```

Dry run without inserting rows:

```bash
gcloud run jobs execute hdvi-folder-backfill \
  --project moove-data-pipelines \
  --region us-central1 \
  --args="--start-date=2025-11-09","--dry-run"
```

Backfill script also honors `BACKFILL_START_DATE` / `BACKFILL_END_DATE` env vars, and sets `DISABLE_COMPLETION_THREAD=true` so the batch container skips long-running monitor threads.

