-- Create schemas
CREATE SCHEMA IF NOT EXISTS mpi;
CREATE SCHEMA IF NOT EXISTS reconciliation;
CREATE SCHEMA IF NOT EXISTS timeline;
CREATE SCHEMA IF NOT EXISTS patient_summary;

-- Create app users
CREATE USER hs_writer WITH PASSWORD 'hs_writer';
CREATE USER hs_reader WITH PASSWORD 'hs_reader';

GRANT CONNECT ON DATABASE healthcare TO hs_writer, hs_reader;
GRANT USAGE ON SCHEMA mpi, reconciliation, timeline, patient_summary TO hs_writer, hs_reader;

-- hs_writer: allow refreshing materialized views (pg_maintain is Postgres 16+)
GRANT pg_maintain TO hs_writer;

-- hs_writer: full DML on all schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA mpi GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA reconciliation GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA timeline GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_summary GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;

-- hs_reader: SELECT only on all schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA mpi GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reconciliation GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA timeline GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_summary GRANT SELECT ON TABLES TO hs_reader;
