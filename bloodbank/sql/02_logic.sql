CREATE OR REPLACE FUNCTION trg_check_donor_eligibility() RETURNS trigger AS $$
DECLARE
    d     donors%ROWTYPE;
    d_age INTEGER;
BEGIN
    SELECT * INTO d FROM donors WHERE id = NEW.donor_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Donor % does not exist', NEW.donor_id;
    END IF;

    IF NEW.donation_date > CURRENT_DATE THEN
        RAISE EXCEPTION 'Donation date % is in the future', NEW.donation_date;
    END IF;

    d_age := EXTRACT(YEAR FROM age(NEW.donation_date, d.dob));

    IF d_age < 18 THEN
        RAISE EXCEPTION 'Donor % is not eligible: age % is below the minimum of 18', d.name, d_age;
    ELSIF d_age > 65 THEN
        RAISE EXCEPTION 'Donor % is not eligible: age % is above the maximum of 65', d.name, d_age;
    END IF;

    IF d.weight_kg < 45 THEN
        RAISE EXCEPTION 'Donor % is not eligible: weight % kg is below the minimum of 45 kg', d.name, d.weight_kg;
    END IF;

    IF d.hemoglobin < 12.5 THEN
        RAISE EXCEPTION 'Donor % is not eligible: hemoglobin % g/dL is below the minimum of 12.5', d.name, d.hemoglobin;
    END IF;

    IF d.last_donation_date IS NOT NULL
       AND NEW.donation_date - d.last_donation_date < 90 THEN
        RAISE EXCEPTION 'Donor % is not eligible: last donated on % (% days ago); must wait 90 days, next eligible on %',
            d.name, d.last_donation_date, NEW.donation_date - d.last_donation_date,
            d.last_donation_date + 90;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_donations_eligibility ON donations;
CREATE TRIGGER trg_donations_eligibility
    BEFORE INSERT ON donations
    FOR EACH ROW EXECUTE FUNCTION trg_check_donor_eligibility();

CREATE OR REPLACE FUNCTION trg_create_blood_unit() RETURNS trigger AS $$
BEGIN
    INSERT INTO blood_units (donation_id, blood_group, collection_date, expiry_date, status)
    SELECT NEW.id, d.blood_group, NEW.donation_date, NEW.donation_date + 35, 'Available'
    FROM donors d
    WHERE d.id = NEW.donor_id;

    UPDATE donors
       SET last_donation_date = GREATEST(COALESCE(last_donation_date, NEW.donation_date), NEW.donation_date)
     WHERE id = NEW.donor_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_donations_create_unit ON donations;
CREATE TRIGGER trg_donations_create_unit
    AFTER INSERT ON donations
    FOR EACH ROW EXECUTE FUNCTION trg_create_blood_unit();

CREATE OR REPLACE FUNCTION mark_expired_units() RETURNS INTEGER AS $$
DECLARE
    n INTEGER;
BEGIN
    UPDATE blood_units
       SET status = 'Expired'
     WHERE status = 'Available'
       AND expiry_date < CURRENT_DATE;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_validate_issue() RETURNS trigger AS $$
DECLARE
    u blood_units%ROWTYPE;
    r blood_requests%ROWTYPE;
BEGIN
    SELECT * INTO u FROM blood_units WHERE id = NEW.unit_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Blood unit % does not exist', NEW.unit_id;
    END IF;
    SELECT * INTO r FROM blood_requests WHERE id = NEW.request_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Request % does not exist', NEW.request_id;
    END IF;

    IF u.status = 'Expired' OR u.expiry_date < CURRENT_DATE THEN
        RAISE EXCEPTION 'Unit % cannot be issued: it expired on %', u.id, u.expiry_date;
    END IF;
    IF u.status <> 'Available' THEN
        RAISE EXCEPTION 'Unit % cannot be issued: status is %', u.id, u.status;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM blood_compatibility
                   WHERE donor_group = u.blood_group
                     AND recipient_group = r.blood_group_needed) THEN
        RAISE EXCEPTION 'Unit % (%) is not compatible with request % needing %',
            u.id, u.blood_group, r.id, r.blood_group_needed;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_issues_validate ON blood_issues;
CREATE TRIGGER trg_issues_validate
    BEFORE INSERT ON blood_issues
    FOR EACH ROW EXECUTE FUNCTION trg_validate_issue();

CREATE OR REPLACE FUNCTION trg_mark_unit_issued() RETURNS trigger AS $$
BEGIN
    UPDATE blood_units SET status = 'Issued' WHERE id = NEW.unit_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_issues_mark_unit ON blood_issues;
CREATE TRIGGER trg_issues_mark_unit
    AFTER INSERT ON blood_issues
    FOR EACH ROW EXECUTE FUNCTION trg_mark_unit_issued();

CREATE OR REPLACE FUNCTION issue_blood(p_request_id INTEGER)
RETURNS TABLE (unit_id INTEGER, blood_group VARCHAR, expiry_date DATE) AS $$
#variable_conflict use_column
DECLARE
    req        blood_requests%ROWTYPE;
    already    INTEGER;
    remaining  INTEGER;
    issued_now INTEGER := 0;
    u          RECORD;
BEGIN
    SELECT * INTO req FROM blood_requests WHERE id = p_request_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Request % does not exist', p_request_id;
    END IF;

    SELECT COUNT(*) INTO already FROM blood_issues bi WHERE bi.request_id = req.id;
    remaining := req.units_needed - already;
    IF remaining <= 0 THEN
        RAISE EXCEPTION 'Request % is already fulfilled', req.id;
    END IF;

    PERFORM mark_expired_units();

    FOR u IN
        SELECT bu.id, bu.blood_group, bu.expiry_date
          FROM blood_units bu
          JOIN blood_compatibility c
            ON c.donor_group = bu.blood_group
           AND c.recipient_group = req.blood_group_needed
         WHERE bu.status = 'Available'
           AND bu.expiry_date >= CURRENT_DATE
         ORDER BY (bu.blood_group = req.blood_group_needed) DESC,
                  bu.expiry_date ASC,
                  bu.id ASC
         LIMIT remaining
           FOR UPDATE OF bu SKIP LOCKED
    LOOP
        INSERT INTO blood_issues (request_id, unit_id, issue_date)
        VALUES (req.id, u.id, CURRENT_DATE);

        UPDATE blood_units bu SET status = 'Issued' WHERE bu.id = u.id;
        issued_now := issued_now + 1;

        unit_id     := u.id;
        blood_group := u.blood_group;
        expiry_date := u.expiry_date;
        RETURN NEXT;
    END LOOP;

    IF already + issued_now >= req.units_needed THEN
        UPDATE blood_requests SET status = 'Fulfilled' WHERE id = req.id;
    ELSIF already + issued_now > 0 THEN
        UPDATE blood_requests SET status = 'Partially Fulfilled' WHERE id = req.id;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW v_stock_summary AS
SELECT g.blood_group,
       COUNT(u.id) AS available_units
FROM (SELECT DISTINCT donor_group AS blood_group FROM blood_compatibility) g
LEFT JOIN blood_units u
       ON u.blood_group = g.blood_group
      AND u.status = 'Available'
      AND u.expiry_date >= CURRENT_DATE
GROUP BY g.blood_group
ORDER BY g.blood_group;

CREATE OR REPLACE VIEW v_near_expiry AS
SELECT u.id AS unit_id,
       u.blood_group,
       u.collection_date,
       u.expiry_date,
       (u.expiry_date - CURRENT_DATE) AS days_left
FROM blood_units u
WHERE u.status = 'Available'
  AND u.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
ORDER BY u.expiry_date, u.id;

CREATE OR REPLACE VIEW v_request_status AS
SELECT r.id AS request_id,
       h.name AS hospital,
       r.patient_name,
       r.blood_group_needed,
       r.units_needed,
       COUNT(i.id) AS units_issued,
       r.units_needed - COUNT(i.id) AS units_remaining,
       r.request_date,
       r.status
FROM blood_requests r
JOIN hospitals h ON h.id = r.hospital_id
LEFT JOIN blood_issues i ON i.request_id = r.id
GROUP BY r.id, h.name
ORDER BY r.id;

CREATE OR REPLACE VIEW v_donor_eligibility AS
SELECT d.id, d.name, d.blood_group,
       EXTRACT(YEAR FROM age(CURRENT_DATE, d.dob))::INTEGER AS age,
       d.weight_kg, d.hemoglobin, d.last_donation_date,
       CASE
           WHEN EXTRACT(YEAR FROM age(CURRENT_DATE, d.dob)) < 18 THEN 'No - under 18'
           WHEN EXTRACT(YEAR FROM age(CURRENT_DATE, d.dob)) > 65 THEN 'No - over 65'
           WHEN d.weight_kg < 45 THEN 'No - weight under 45 kg'
           WHEN d.hemoglobin < 12.5 THEN 'No - hemoglobin below 12.5'
           WHEN d.last_donation_date IS NOT NULL
                AND CURRENT_DATE - d.last_donation_date < 90
                THEN 'No - eligible again on ' || (d.last_donation_date + 90)
           ELSE 'Yes'
       END AS eligible
FROM donors d
ORDER BY d.id;
