DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM donors) THEN
        RAISE NOTICE 'Seed data already present - skipping';
        RETURN;
    END IF;

    INSERT INTO donors (name, dob, gender, phone, blood_group, weight_kg, hemoglobin) VALUES
        ('Aarav Sharma',   '1990-04-12', 'Male',   '9810000001', 'A+',  72.0, 14.5),
        ('Priya Nair',     '1995-08-23', 'Female', '9810000002', 'A+',  58.0, 13.2),
        ('Vikram Singh',   '1988-01-05', 'Male',   '9810000003', 'A-',  80.0, 15.1),
        ('Ananya Iyer',    '1999-11-30', 'Female', '9810000004', 'A-',  44.0, 12.9),
        ('Rahul Verma',    '1992-06-17', 'Male',   '9810000005', 'B+',  68.0, 14.0),
        ('Sneha Kulkarni', '1997-03-09', 'Female', '9810000006', 'B+',  52.0, 13.0),
        ('Arjun Reddy',    '1985-09-21', 'Male',   '9810000007', 'B-',  77.0, 14.8),
        ('Meera Joshi',    '1993-12-02', 'Female', '9810000008', 'AB+', 60.0, 13.6),
        ('Karan Malhotra', '1980-07-14', 'Male',   '9810000009', 'AB+', 85.0, 15.3),
        ('Divya Menon',    '2000-02-27', 'Female', '9810000010', 'AB-', 55.0, 13.1),
        ('Imran Khan',     '1987-05-19', 'Male',   '9810000011', 'O+',  74.0, 14.2),
        ('Rohan Mehta',    (CURRENT_DATE - INTERVAL '17 years')::date,
                                         'Male',   '9810000012', 'O+',  61.0, 13.8),
        ('Kavita Rao',     '1991-10-08', 'Female', '9810000013', 'O+',  50.0, 11.4),
        ('Sanjay Gupta',   '1983-03-25', 'Male',   '9810000014', 'O-',  70.0, 14.6),
        ('Neha Bansal',    '1996-07-11', 'Female', '9810000015', 'O-',  56.0, 13.4);

    INSERT INTO donations (donor_id, donation_date, volume_ml)
    SELECT d.id, CURRENT_DATE - x.days_ago, x.volume
    FROM (VALUES
        ('9810000003', 130, 450),
        ('9810000010', 100, 450),
        ('9810000014',  40, 450),
        ('9810000008',  32, 350),
        ('9810000001',  30, 450),
        ('9810000005',  29, 450),
        ('9810000007',  25, 450),
        ('9810000011',  20, 450),
        ('9810000003',  18, 450),
        ('9810000015',  15, 450),
        ('9810000002',  10, 350),
        ('9810000006',   5, 350)
    ) AS x(phone, days_ago, volume)
    JOIN donors d ON d.phone = x.phone
    ORDER BY x.days_ago DESC;

    INSERT INTO hospitals (name, city, phone) VALUES
        ('City General Hospital',      'Mumbai',    '02240000001'),
        ('Lakeview Medical Centre',    'Pune',      '02040000002'),
        ('St. Mary''s Hospital',       'Bengaluru', '08040000003'),
        ('Green Valley Clinic',        'Chennai',   '04440000004'),
        ('Sunrise Children''s Hospital','Delhi',    '01140000005');

    INSERT INTO blood_requests (hospital_id, patient_name, blood_group_needed, units_needed, request_date)
    SELECT h.id, x.patient, x.grp, x.units, CURRENT_DATE - x.days_ago
    FROM (VALUES
        (1, 'City General Hospital',   'Ramesh Patil', 'A+', 2, 1),
        (2, 'Lakeview Medical Centre', 'Fatima Shaikh','O-', 2, 1),
        (3, 'St. Mary''s Hospital',    'George Thomas','B+', 3, 0)
    ) AS x(ord, hospital, patient, grp, units, days_ago)
    JOIN hospitals h ON h.name = x.hospital
    ORDER BY x.ord;
END;
$$;
