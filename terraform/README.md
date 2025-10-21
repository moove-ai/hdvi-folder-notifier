# HDVI Folder Notifier - Terraform Configuration

This Terraform configuration sets up the infrastructure for the HDVI Folder Notifier Cloud Run service.

## What It Creates

1. **Service Account**: `hdvi-folder-notifier-invoker` for Pub/Sub to invoke Cloud Run
2. **Pub/Sub Subscription**: Push subscription to `hdvi-process-incoming` topic
3. **IAM Bindings**:
   - Cloud Run Invoker role for the Pub/Sub service account
   - Firestore User role for the Cloud Run service account

## Prerequisites

1. **Enable required APIs**:
   ```bash
   gcloud services enable \
     run.googleapis.com \
     pubsub.googleapis.com \
     firestore.googleapis.com \
     secretmanager.googleapis.com \
     cloudbuild.googleapis.com \
     --project=moove-data-pipelines
   ```

2. **Build container image first** (in moove-build project):
   ```bash
   cd ..
   gcloud builds submit --project=moove-build --config=cloudbuild.yaml
   ```

3. **Authentication**:
   ```bash
   gcloud auth application-default login
   ```

## Usage

### Initialize Terraform

```bash
cd terraform
terraform init
```

### Review the Plan

```bash
terraform plan
```

### Apply Configuration

```bash
terraform apply
```

### Destroy (if needed)

```bash
terraform destroy
```

## Configuration

Edit `terraform.tfvars` to customize:

```hcl
project_id  = "moove-data-pipelines"
region      = "us-central1"
environment = "production"

service_name      = "hdvi-folder-notifier"
topic_name        = "hdvi-process-incoming"
subscription_name = "hdvi-folder-notifier-sub"

# Monitoring configuration
bucket_name        = "your-bucket-name"
monitored_prefixes = "YourFolder1/,YourFolder2/"
```

## Firestore Database

Terraform will automatically create the Firestore database if it doesn't exist.

**Important Notes:**
- Firestore databases have `lifecycle.prevent_destroy = true` to prevent accidental deletion
- You can only have one Firestore database per project named "(default)"
- If the database already exists, Terraform will import it
- To delete: Set `prevent_destroy = false` first, then destroy (or delete via Console)

**First-time setup:**
```bash
# Terraform will create it automatically
terraform apply
```

**If database already exists:**
```bash
# Import existing database to Terraform state
terraform import google_firestore_database.database "(default)"
```

## State Management

### Local State (Default)

State is stored locally in `terraform.tfstate`. **Do not commit this file to git** (already in `.gitignore`).

### Remote State (Recommended for Teams)

Configure a GCS backend:

```hcl
terraform {
  backend "gcs" {
    bucket = "moove-terraform-state"
    prefix = "hdvi-folder-notifier"
  }
}
```

## Outputs

After applying, you'll see:

```
pubsub_invoker_service_account = "hdvi-folder-notifier-invoker@moove-data-pipelines.iam.gserviceaccount.com"
subscription_name              = "hdvi-folder-notifier-sub"
cloud_run_service_url          = "https://hdvi-folder-notifier-xxx-uc.a.run.app"
topic_name                     = "hdvi-process-incoming"
```

## Validation

### Check Subscription

```bash
gcloud pubsub subscriptions describe hdvi-folder-notifier-sub \
  --project=moove-data-pipelines
```

### Test the Setup

```bash
cd ..
./test-notification.sh Prebind/2024/10/20
```

## Troubleshooting

### Error: Cloud Run service not found

Deploy the Cloud Run service first:
```bash
cd ..
./deploy.sh
```

### Error: Firestore not found

Create the Firestore database:
```bash
gcloud firestore databases create \
  --project=moove-data-pipelines \
  --location=us-central1 \
  --type=firestore-native
```

### Error: Topic not found

Verify the topic exists:
```bash
gcloud pubsub topics describe hdvi-process-incoming \
  --project=moove-data-pipelines
```

## Integration with moove-terraform

To integrate with your main Terraform repo, you can:

1. **Copy module to moove-terraform**:
   ```bash
   cp -r terraform /path/to/moove-terraform/modules/hdvi-folder-notifier
   ```

2. **Use as a module**:
   ```hcl
   module "hdvi_folder_notifier" {
     source = "./modules/hdvi-folder-notifier"
     
     project_id  = "moove-data-pipelines"
     region      = "us-central1"
     environment = "production"
   }
   ```

## Cost

Terraform itself is free. The created resources cost:
- Service account: Free
- Pub/Sub subscription: ~$0.50/month
- IAM bindings: Free
- Firestore: ~$0.50/month

Total: ~$1/month

