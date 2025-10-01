-- Seed RBAC roles and permissions
INSERT INTO roles (name, description) VALUES
  ('Basic',   'Basic user with limited access'),
  ('Premium', 'Premium user with full features'),
  ('Admin',   'Administrator with full control')
ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (resource, action) VALUES
  ('market',   'candles:read'),
  ('market',   'option_chain:read'),
  ('simulator','run:write'),
  ('simulator','export:read'),
  ('portfolio','read'),
  ('portfolio','write'),
  ('stats',    'basic:read'),
  ('stats',    'risk:read'),
  ('ml',       'predict:read'),
  ('explain',  'shap:read'),
  ('admin',    'users:write'),
  ('admin',    'roles:write'),
  ('admin',    'audit:read'),
  ('admin',    'services:read')
ON CONFLICT (resource, action) DO NOTHING;

-- Map Basic role permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON (p.resource, p.action) IN (
    ('market', 'candles:read'),
    ('market', 'option_chain:read'),
    ('simulator', 'run:write'),
    ('portfolio', 'read'),
    ('stats', 'basic:read')
)
WHERE r.name = 'Basic'
ON CONFLICT DO NOTHING;

-- Map Premium role permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON (p.resource, p.action) IN (
    ('market', 'candles:read'),
    ('market', 'option_chain:read'),
    ('simulator', 'run:write'),
    ('simulator', 'export:read'),
    ('portfolio', 'read'),
    ('portfolio', 'write'),
    ('stats', 'basic:read'),
    ('stats', 'risk:read'),
    ('ml', 'predict:read'),
    ('explain', 'shap:read')
)
WHERE r.name = 'Premium'
ON CONFLICT DO NOTHING;

-- Map Admin role permissions (all permissions)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'Admin'
ON CONFLICT DO NOTHING;
