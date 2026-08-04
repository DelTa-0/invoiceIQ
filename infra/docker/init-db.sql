-- InvoiceIQ local-dev database bootstrap.
-- Mounted at /docker-entrypoint-initdb.d/ so it runs once on first container start.
-- Creates the NON-superuser application role: Row-Level Security is bypassed
-- for superusers, so the API/worker must connect as this limited role for the
-- org-isolation policies (see alembic 0001) to actually enforce tenancy.

-- Migrations (alembic upgrade head) are run separately by a privileged role.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'invoiceiq_app') THEN
    CREATE ROLE invoiceiq_app LOGIN PASSWORD 'invoiceiq' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END
$$;

GRANT CONNECT ON DATABASE invoiceiq TO invoiceiq_app;
GRANT USAGE ON SCHEMA public TO invoiceiq_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO invoiceiq_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO invoiceiq_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO invoiceiq_app;
