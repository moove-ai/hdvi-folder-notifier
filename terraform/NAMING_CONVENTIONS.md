# Resource Naming Conventions

This document describes the naming conventions used for all resources in the HDVI Folder Notifier infrastructure.

## Naming Pattern

All resources follow this pattern:
```
hdvi-folder-notifier-<type>
```

## Resource Names

### Cloud Run
- **Service Name**: `hdvi-folder-notifier`
- **Why**: Clear, descriptive, follows kebab-case convention
- **Format**: `hdvi-folder-notifier`

### Service Accounts
- **Pub/Sub Invoker**: `hdvi-folder-notifier-invoker`
- **Why**: Describes the purpose (invoke Cloud Run from Pub/Sub)
- **Format**: `<service>-<purpose>`

### Pub/Sub
- **Subscription**: `hdvi-folder-notifier-sub`
- **Why**: Links to the service it serves
- **Format**: `<service>-sub`
- **Note**: Topic name `hdvi-process-incoming` is pre-existing

### Secret Manager
- **Secret Name**: `hdvi-folder-notifier-slack-webhook`
- **Why**: Describes what the secret contains
- **Format**: `<service>-<secret-type>`

### Firestore
- **Database Name**: `(default)`
- **Why**: Standard Firestore naming (only one per project)
- **Collection**: `notified_folders`
- **Why**: Describes what data is stored

## Labels

All resources are labeled with:
```hcl
labels = {
  terraformed = "true"      # Managed by Terraform
  environment = "production" # Environment name
  service     = "hdvi-folder-notifier" # Service name
  app         = "hdvi-folder-notifier" # Application identifier
  managed-by  = "terraform"  # Management tool
}
```

## IAM Roles

- **Cloud Run Invoker**: For Pub/Sub service account to invoke Cloud Run
- **Firestore User**: For Cloud Run service account to read/write Firestore
- **Secret Accessor**: For Cloud Run service account to read secrets

## Variable Naming

Terraform variables follow snake_case:
```hcl
service_name              # Not serviceName or service-name
cloud_run_service_account # Clear and descriptive
pubsub_invoker_sa_name    # Service account specific
```

## Why These Conventions?

1. **Consistency**: All resources follow the same pattern
2. **Clarity**: Names describe purpose and relationships
3. **Searchability**: Easy to find related resources
4. **GCP Compliance**: Follow Google Cloud naming best practices
5. **Team Collaboration**: Clear naming aids understanding

## Changing Names

If you need different names, update `terraform.tfvars`:

```hcl
service_name           = "my-custom-notifier"
subscription_name      = "my-custom-notifier-sub"
pubsub_invoker_sa_name = "my-custom-notifier-invoker"
```

All dependent resources will use the new names automatically.

## Best Practices

1. **Use lowercase**: GCP resources prefer lowercase
2. **Use hyphens**: For kebab-case (not underscores in resource names)
3. **Be descriptive**: Name should indicate purpose
4. **Include project context**: `hdvi` indicates this is for HDVI data
5. **Limit length**: Keep under 63 characters for compatibility
6. **Avoid special characters**: Stick to alphanumeric and hyphens
7. **Include environment**: Use labels, not names (names are in tfvars)

## Examples from Other Projects

Good:
- `weather-etl-processor`
- `batch-upload-handler`
- `data-validation-service`

Bad:
- `service1` (not descriptive)
- `my_service` (underscores in resource name)
- `MyService` (capitals not standard)
- `hdvi-folder-notifier-for-production-use` (too long)

