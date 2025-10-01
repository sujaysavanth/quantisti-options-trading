# Security RBAC Policy

This document outlines the role-based access control (RBAC) model for the Quantisti options trading platform.

## Roles
- **Basic** – Entry-level access for general market visibility.
- **Premium** – Enhanced access for paid subscribers.
- **Admin** – Full administrative control over the platform.

## Permissions
Permissions are defined by the `resource:action` pair.

| Resource | Actions |
|----------|---------|
| `market` | `candles:read`, `option_chain:read` |
| `simulator` | `run:write`, `export:read` |
| `portfolio` | `read`, `write` |
| `stats` | `basic:read`, `risk:read` |
| `ml` | `predict:read` |
| `explain` | `shap:read` |
| `admin` | `users:write`, `roles:write`, `audit:read`, `services:read` |

## Role to Permission Matrix

| Role    | Permissions |
|---------|-------------|
| **Basic** | `market:candles:read`, `market:option_chain:read`, `simulator:run:write`, `portfolio:read`, `stats:basic:read` |
| **Premium** | All **Basic** permissions plus `simulator:export:read`, `portfolio:write`, `stats:risk:read`, `ml:predict:read`, `explain:shap:read` |
| **Admin** | All permissions including all `admin:*` capabilities |

- Basic users do **not** receive access to simulator exports, premium analytics, ML, explainability, or admin endpoints.
- Premium users gain all Basic access along with additional analytics, ML, explainability, and export capabilities.
- Admin users receive full access, including administrative management and observability endpoints.

## Route Map

| Route Pattern | Required Permission |
|---------------|---------------------|
| `/market/candles` | `market:candles:read` |
| `/market/option-chain` | `market:option_chain:read` |
| `/simulate/*` | `simulator:run:write` |
| `/simulate/{id}/export` | `simulator:export:read` |
| `/portfolio/*` (GET) | `portfolio:read` |
| `/portfolio/*` (POST/PUT/PATCH) | `portfolio:write` |
| `/stats/basic/*` | `stats:basic:read` |
| `/stats/risk/*` | `stats:risk:read` |
| `/ml/predict` | `ml:predict:read` |
| `/explain/shap` | `explain:shap:read` |
| `/admin/users/*` | `admin:users:write` |
| `/admin/roles/*` | `admin:roles:write` |
| `/admin/audit` | `admin:audit:read` |
| `/admin/services/health` | `admin:services:read` |

