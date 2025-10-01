-- Sample data for local testing (comment out in production environments)
INSERT INTO users (uid, email) VALUES
  ('user_basic_1', 'basic@example.com'),
  ('user_premium_1', 'premium@example.com'),
  ('user_admin_1', 'admin@example.com')
ON CONFLICT (uid) DO NOTHING;

INSERT INTO user_roles (user_uid, role_id)
SELECT 'user_basic_1', id FROM roles WHERE name = 'Basic'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_uid, role_id)
SELECT 'user_premium_1', id FROM roles WHERE name = 'Premium'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_uid, role_id)
SELECT 'user_admin_1', id FROM roles WHERE name = 'Admin'
ON CONFLICT DO NOTHING;
