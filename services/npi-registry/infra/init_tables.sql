-- NPI Registry: provider master table
CREATE TABLE IF NOT EXISTS npi_registry.providers (
    npi         TEXT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    title       TEXT NOT NULL,
    specialty   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed test providers (actual NPIs are 10 digits, these are fictional for testing)
INSERT INTO npi_registry.providers (npi, first_name, last_name, title, specialty)
VALUES
    ('1111111111', 'John', 'Smith', 'MD', 'Cardiology'),
    ('2222222222', 'Jane', 'Doe', 'DO', 'Orthopedics'),
    ('3333333333', 'Robert', 'Johnson', 'MD', 'Psychiatry'),
    ('4444444444', 'Maria', 'Garcia', 'MD', 'Pediatrics'),
    ('5555555555', 'David', 'Lee', 'MD', 'Neurology'),
    ('6666666666', 'Sarah', 'Williams', 'MD', 'Dermatology'),
    ('7777777777', 'Michael', 'Brown', 'DO', 'Internal Medicine'),
    ('8888888888', 'Jennifer', 'Davis', 'MD', 'Oncology'),
    ('9999999999', 'Christopher', 'Miller', 'MD', 'Radiology'),
    ('1010101010', 'Amanda', 'Wilson', 'PA', 'Surgery')
ON CONFLICT DO NOTHING;
