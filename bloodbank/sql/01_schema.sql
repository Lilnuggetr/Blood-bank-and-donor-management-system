CREATE TABLE IF NOT EXISTS donors (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    dob                 DATE         NOT NULL CHECK (dob < CURRENT_DATE),
    gender              VARCHAR(10)  NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    phone               VARCHAR(20)  NOT NULL UNIQUE,
    blood_group         VARCHAR(3)   NOT NULL
                        CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    weight_kg           NUMERIC(5,1) NOT NULL CHECK (weight_kg > 0),
    hemoglobin          NUMERIC(4,1) NOT NULL CHECK (hemoglobin > 0),
    last_donation_date  DATE
);

CREATE TABLE IF NOT EXISTS donations (
    id             SERIAL PRIMARY KEY,
    donor_id       INTEGER NOT NULL REFERENCES donors(id) ON DELETE RESTRICT,
    donation_date  DATE    NOT NULL DEFAULT CURRENT_DATE,
    volume_ml      INTEGER NOT NULL DEFAULT 450 CHECK (volume_ml > 0)
);

CREATE TABLE IF NOT EXISTS blood_units (
    id               SERIAL PRIMARY KEY,
    donation_id      INTEGER     NOT NULL UNIQUE REFERENCES donations(id) ON DELETE RESTRICT,
    blood_group      VARCHAR(3)  NOT NULL
                     CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    collection_date  DATE        NOT NULL,
    expiry_date      DATE        NOT NULL,
    status           VARCHAR(10) NOT NULL DEFAULT 'Available'
                     CHECK (status IN ('Available', 'Issued', 'Expired')),
    CHECK (expiry_date > collection_date)
);

CREATE TABLE IF NOT EXISTS hospitals (
    id     SERIAL PRIMARY KEY,
    name   VARCHAR(120) NOT NULL UNIQUE,
    city   VARCHAR(60)  NOT NULL,
    phone  VARCHAR(20)  NOT NULL
);

CREATE TABLE IF NOT EXISTS blood_requests (
    id                  SERIAL PRIMARY KEY,
    hospital_id         INTEGER      NOT NULL REFERENCES hospitals(id) ON DELETE RESTRICT,
    patient_name        VARCHAR(100) NOT NULL,
    blood_group_needed  VARCHAR(3)   NOT NULL
                        CHECK (blood_group_needed IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units_needed        INTEGER      NOT NULL CHECK (units_needed > 0),
    request_date        DATE         NOT NULL DEFAULT CURRENT_DATE,
    status              VARCHAR(20)  NOT NULL DEFAULT 'Pending'
                        CHECK (status IN ('Pending', 'Fulfilled', 'Partially Fulfilled'))
);

CREATE TABLE IF NOT EXISTS blood_issues (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES blood_requests(id) ON DELETE RESTRICT,
    unit_id     INTEGER NOT NULL UNIQUE REFERENCES blood_units(id) ON DELETE RESTRICT,
    issue_date  DATE    NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS blood_compatibility (
    donor_group      VARCHAR(3) NOT NULL
                     CHECK (donor_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    recipient_group  VARCHAR(3) NOT NULL
                     CHECK (recipient_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    PRIMARY KEY (donor_group, recipient_group)
);

INSERT INTO blood_compatibility (donor_group, recipient_group)
SELECT d.g, r.g
FROM (VALUES ('A+'),('A-'),('B+'),('B-'),('AB+'),('AB-'),('O+'),('O-')) AS d(g)
CROSS JOIN (VALUES ('A+'),('A-'),('B+'),('B-'),('AB+'),('AB-'),('O+'),('O-')) AS r(g)
WHERE (left(d.g, length(d.g) - 1) = 'O'
       OR left(d.g, length(d.g) - 1) = left(r.g, length(r.g) - 1)
       OR left(r.g, length(r.g) - 1) = 'AB')
  AND (right(d.g, 1) = '-' OR right(r.g, 1) = '+')
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_donations_donor     ON donations (donor_id);
CREATE INDEX IF NOT EXISTS idx_units_fefo          ON blood_units (blood_group, expiry_date) WHERE status = 'Available';
CREATE INDEX IF NOT EXISTS idx_units_status_expiry ON blood_units (status, expiry_date);
CREATE INDEX IF NOT EXISTS idx_requests_hospital   ON blood_requests (hospital_id);
CREATE INDEX IF NOT EXISTS idx_requests_status     ON blood_requests (status);
CREATE INDEX IF NOT EXISTS idx_issues_request      ON blood_issues (request_id);
