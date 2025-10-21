# Cloud Build trigger for automatic builds on GitHub push
resource "google_cloudbuild_trigger" "github_push" {
  count           = var.enable_github_triggers ? 1 : 0
  name            = "hdvi-folder-notifier-github"
  location        = "global"
  project         = "moove-build"
  service_account = "projects/moove-build/serviceAccounts/deployer@moove-build.iam.gserviceaccount.com"
  description     = "Builds hdvi-folder-notifier on GitHub push to main"
  included_files  = ["**"]
  ignored_files   = ["README.md", "*.md", "terraform/**"]
  tags            = ["hdvi-folder-notifier", "github"]
  disabled        = false
  filename        = "cloudbuild.yaml"

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^main$"
    }
  }

  substitutions = {
    _SERVICE_NAME = "hdvi-folder-notifier"
  }
}

# Optional: Pull Request trigger for testing
resource "google_cloudbuild_trigger" "github_pr" {
  count           = var.enable_github_triggers ? 1 : 0
  name            = "hdvi-folder-notifier-pr"
  location        = "global"
  project         = "moove-build"
  service_account = "projects/moove-build/serviceAccounts/deployer@moove-build.iam.gserviceaccount.com"
  description     = "Builds hdvi-folder-notifier on GitHub pull requests"
  included_files  = ["**"]
  ignored_files   = ["README.md", "*.md", "terraform/**"]
  tags            = ["hdvi-folder-notifier", "github", "pr"]
  disabled        = false
  filename        = "cloudbuild.yaml"

  github {
    owner = var.github_owner
    name  = var.github_repo
    pull_request {
      branch          = "^main$"
      comment_control = "COMMENTS_ENABLED"
    }
  }

  substitutions = {
    _SERVICE_NAME = "hdvi-folder-notifier"
  }
}
