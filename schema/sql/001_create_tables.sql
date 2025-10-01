-- RBAC core tables
CREATE TABLE IF NOT EXISTS users (
    uid TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    CONSTRAINT permissions_uniq UNIQUE (resource, action)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_uid TEXT NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_uid, role_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_uid TEXT,
    resource TEXT,
    action TEXT,
    decision TEXT CHECK (decision IN ('allow', 'deny')),
    trace_id TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Optional trigger to update users.updated_at could be added here if needed.

CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_uid);
CREATE INDEX IF NOT EXISTS idx_role_perms_role ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_permissions_resource_action ON permissions(resource, action);
