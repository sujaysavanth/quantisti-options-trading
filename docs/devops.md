# DevOps Overview

This document outlines the high-level DevOps workflow for the Quantisti options trading platform.

## Continuous Integration
- GitHub Actions workflow `.github/workflows/ci.yml` runs on pull requests and pushes to `main`.
- For each service, the pipeline:
  - Installs the service in editable mode (`pip install -e .`).
  - Executes placeholder linting commands (to be replaced with real tooling).
  - Runs `pytest -q || true` to avoid failures while tests are unavailable.
- Docker images for each service are built locally to ensure Dockerfiles remain healthy.

## Deployment to Google Cloud Run
- A manual `workflow_dispatch` GitHub Action (`deploy-cloudrun.yml`) will orchestrate deployments.
- Planned steps (all marked TODO in the workflow):
  - Authenticate to Google Cloud using workload identity or a service account key.
  - Configure the active project and region.
  - Build and push container images to Artifact Registry.
  - Deploy the selected service using `gcloud run deploy`.
- Firebase authentication and Cloud SQL integrations will be wired in during future iterations.

## Observability
- Stackdriver / Cloud Logging will be enabled per service once infrastructure is ready.
- TODO: Add log correlation, metrics exporters, and alerting policies.

## Next Steps
- Flesh out Terraform definitions to manage Cloud Run services and supporting infrastructure.
- Harden Docker images and add automated security scanning.
- Implement end-to-end tests and contract tests for service interactions.
