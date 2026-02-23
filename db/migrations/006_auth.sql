ALTER TABLE customers ADD COLUMN name TEXT;
ALTER TABLE customers ADD COLUMN avatar_url TEXT;
ALTER TABLE customers ADD COLUMN auth_provider TEXT;
ALTER TABLE customers ADD COLUMN auth_provider_id TEXT;
CREATE UNIQUE INDEX ix_customers_auth ON customers(auth_provider, auth_provider_id) WHERE auth_provider IS NOT NULL;
