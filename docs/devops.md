# DevOps Overview

This document outlines the high-level DevOps workflow for the Quantisti options trading platform.

## Continuous Integration
GitHub Actions (`.github/workflows/ci.yml`) runs on every push to any branch and on pull requests. Every job is
blocking; a newer push to the same branch cancels the older run.
- **python-tests**: market, simulator, ml and ingest, each with `pip install -e ".[test]"` and `pytest -q`.
- **spark-tests**: builds the stream-processing image and runs its tests against a Postgres service container
  with `schema/sql` applied (`REQUIRE_POSTGRES=1`, so the database tests fail rather than skip).
- **lint**: `ruff check services scripts` with the rules in `ruff.toml` (syntax errors and pyflakes).
- **frontend**: `npm ci` and `npm run build` (including the TypeScript check) for `landing` and `strategy-dashboard`.
- **docker-build**: every service image, with GitHub Actions build caching.

To keep red builds out of `main`, require these checks in Settings -> Branches.

## Deployment to Google Cloud Run (planned, not built)
- A manual deploy workflow will be added once deployment is real. Planned steps:
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
