# RBAC Schema Setup

This directory contains SQL files and documentation for applying the role-based access control (RBAC) schema.

## Prerequisites
- A reachable PostgreSQL instance.
- `DATABASE_URL` environment variable pointing to the target database.

## Optional: Start a local PostgreSQL instance
If you need a local database, you can launch one with the provided Compose overlay:

```bash
docker compose -f docker-compose.db.yml up -d
```

## Configure database connection
Export your database connection string before applying migrations. Example for the local Compose service:

```bash
export DATABASE_URL=postgresql://quantisti:quantisti@localhost:5432/quantisti
```

## Apply schema and seed data
Run the helper script to apply all SQL files in order:

```bash
bash scripts/db_apply.sh
```

## Verify the schema
Use `psql` to inspect the resulting tables and permissions:

```bash
psql "$DATABASE_URL" -c "TABLE roles;"
psql "$DATABASE_URL" -c "SELECT r.name, p.resource, p.action\n                       FROM roles r\n                       JOIN role_permissions rp ON rp.role_id = r.id\n                       JOIN permissions p ON p.id = rp.permission_id\n                       ORDER BY r.name, p.resource, p.action;"
```
