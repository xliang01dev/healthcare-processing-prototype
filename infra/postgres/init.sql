-- Create schemas
CREATE SCHEMA IF NOT EXISTS patient_data;
CREATE SCHEMA IF NOT EXISTS patient_event_reconciliation;
CREATE SCHEMA IF NOT EXISTS patient_timeline;
CREATE SCHEMA IF NOT EXISTS patient_summary;
CREATE SCHEMA IF NOT EXISTS npi_registry;

-- Create app users
CREATE USER hs_writer WITH PASSWORD 'hs_writer';
CREATE USER hs_reader WITH PASSWORD 'hs_reader';

GRANT CONNECT ON DATABASE healthcare TO hs_writer, hs_reader;
GRANT USAGE ON SCHEMA patient_data, patient_event_reconciliation, patient_timeline, patient_summary, npi_registry TO hs_writer, hs_reader;

-- hs_writer: full DML on all schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_data GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_event_reconciliation GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_timeline GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_summary GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA npi_registry GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hs_writer;

-- hs_writer: USAGE on sequences (for BIGSERIAL auto-increment)
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_data GRANT USAGE ON SEQUENCES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_event_reconciliation GRANT USAGE ON SEQUENCES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_timeline GRANT USAGE ON SEQUENCES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_summary GRANT USAGE ON SEQUENCES TO hs_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA npi_registry GRANT USAGE ON SEQUENCES TO hs_writer;

-- hs_reader: SELECT only on all schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_data GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_event_reconciliation GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_timeline GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA patient_summary GRANT SELECT ON TABLES TO hs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA npi_registry GRANT SELECT ON TABLES TO hs_reader;
