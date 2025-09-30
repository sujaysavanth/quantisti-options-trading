# Getting Started

This guide outlines how to set up the Quantisti options trading backend services for local development.

## Prerequisites
- Docker and Docker Compose
- Python 3.11 (for running tooling locally if needed)
- A POSIX-compatible shell (for helper scripts)

## Local Development
1. Copy `.env.example` to `.env` and populate values when available.
2. Build and start the services:
   ```bash
   ./scripts/dev_up.sh
   ```
   > **Note:** Mark the script as executable with `chmod +x scripts/dev_up.sh` before running.
3. Access the health endpoints of each service to verify they are running.
4. When finished, stop the services:
   ```bash
   ./scripts/dev_down.sh
   ```

## Service Endpoints
The default port assignments are:
- Gateway: http://localhost:8080
- Market: http://localhost:8081
- Simulator: http://localhost:8082
- Portfolio: http://localhost:8083
- Stats: http://localhost:8084
- ML: http://localhost:8085
- Explain: http://localhost:8086

Health endpoints are available under `/health/healthz` and `/health/readyz` for each service.

## Adding a New Service
To introduce a new microservice:
1. Create a directory under `services/<service-name>/` with an `app/` package, `routers/` folder, and placeholder README.
2. Scaffold a `pyproject.toml` listing FastAPI and Uvicorn dependencies.
3. Add a Dockerfile mirroring the existing services and assign the next available port.
4. Update `docker-compose.yml` and CI workflows to include the new service.
