# Blood Bank & Donor Management System

DBMS mini project: Python (Tkinter + psycopg2) on PostgreSQL 16.

**Problem.** Blood banks that track donors and stock by hand let donors give blood too early, miss expired or nearly expired units, and issue blood without checking compatibility.
**Solution.** One database for donors, donations, blood units and hospital requests. The **database itself** enforces eligibility, expiry and compatibility, and issues blood **First-Expiry-First-Out (FEFO)** to cut wastage. The Python app only calls the database and shows the results or the database's error messages.

## Running without Docker (local PostgreSQL + pgAdmin)

You don't need Docker. You do need a **PostgreSQL server**, because pgAdmin is only a viewer. On Windows the PostgreSQL installer usually installs pgAdmin too, so check pgAdmin for a local server (e.g. "PostgreSQL 16") that connects with your password. If you don't have one, install PostgreSQL from https://www.postgresql.org/download/ (version 13 or newer; 16 matches this project).

1. Copy only the `bloodbank` folder. You don't need `pg-docker`.
2. Create `bloodbank/.env` containing **your own** PostgreSQL password (the one you chose when installing PostgreSQL):
   ```
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password_here
   ```
   If your server isn't on port 5432, also add a line such as `DB_PORT=5433`.
3. Install the packages and set up the database:
   ```powershell
   cd bloodbank
   pip install -r requirements.txt
   python init_db.py      # creates the `bloodbank` database and runs all the SQL files
   ```
4. Start the app:
   ```powershell
   python app.py
   ```

The `bloodbank` database then appears in pgAdmin under your local server (right-click → *Refresh* if it isn't there). You don't have to create anything by hand in pgAdmin. Ignore the pgAdmin address `http://localhost:5050` mentioned below: it only applies to the Docker setup. Use your installed pgAdmin app instead.

## Setup

Requirements: the existing Docker setup in `../pg-docker` must be running (Postgres on `localhost:5432`, pgAdmin on `http://localhost:5050`), plus Python 3.

```powershell
cd "C:\DBMS MINI PROJECT\bloodbank"
pip install -r requirements.txt
python init_db.py      # creates database `bloodbank`, runs sql/01..03, lists every object
python app.py          # opens the UI
python test_flows.py   # optional: 12 automated checks of the rules (rolled back afterwards)
```

**Credentials.** `db.py` loads them with python-dotenv, using the first file it finds from this list:

1. the file named in the `BLOODBANK_ENV_FILE` environment variable
2. `bloodbank/.env`
3. `../pg-docker/.env`, which is the Docker setup's file

It reads `POSTGRES_USER` and `POSTGRES_PASSWORD`. The password is never printed and is not written in any source file. `.env` is listed in `.gitignore`.

`init_db.py` is safe to re-run. It creates only what is missing, replaces the functions and views, and skips the seed data if donors already exist. Nothing is ever dropped.

### Seeing the connection in pgAdmin
Open http://localhost:5050. The server **Local Postgres 16** is already registered. Expand *Databases → bloodbank → Schemas → public* to see the Tables, Views, Functions and Trigger Functions.
While `app.py` is running, open *Dashboard → Sessions* (or run the first demo query below). It shows a session named **`bloodbank_app`**: the Python app's live connection. The app's status bar shows the same thing, and it re-checks the connection every 5 seconds.

## Files

| File | Purpose |
|---|---|
| `sql/01_schema.sql` | Tables, PK/FK, NOT NULL, CHECK, UNIQUE, indexes, compatibility data |
| `sql/02_logic.sql` | Triggers, functions (`mark_expired_units`, `issue_blood`) and views |
| `sql/03_seed.sql` | Sample data, with dates relative to today so the demo works on any day |
| `init_db.py` | Creates the DB if missing, runs the 3 SQL files, verifies the objects |
| `db.py` | The one connection helper (parameterized queries, exact DB error text) |
| `app.py` | Tkinter UI: Donors, Donations, Stock, Requests, Issue Blood tabs + status bar |
| `test_flows.py` | End-to-end checks of every rule from Python |
| `docs/er_diagram.md` | Mermaid ER diagram |

## Tables (3NF)

Every non-key column depends only on its own table's key. Shared facts are stored once: the hospital's name lives in `hospitals`, a donor's details live in `donors`, and the compatibility rules live in `blood_compatibility`.

| Table | Holds | Key constraints |
|---|---|---|
| `donors` | One row per donor: dob, gender, phone, blood group, weight, hemoglobin, last donation date | `phone` UNIQUE; CHECKs on gender, blood group, weight > 0, hemoglobin > 0, dob in past |
| `donations` | Each donation event | FK → donors; `volume_ml > 0`; eligibility trigger runs before every insert |
| `blood_units` | The physical bag created from a donation | FK → donations, **UNIQUE** (1 donation = 1 unit); status ∈ Available/Issued/Expired; `expiry_date > collection_date` |
| `hospitals` | Hospitals that request blood | `name` UNIQUE |
| `blood_requests` | A hospital's request for a patient | FK → hospitals; `units_needed > 0`; status ∈ Pending/Fulfilled/Partially Fulfilled |
| `blood_issues` | Which unit went to which request (links requests and units) | FK → requests, FK → units with **UNIQUE unit_id** (a unit can't be issued twice) |
| `blood_compatibility` | 27 rows of standard ABO/Rh red-cell compatibility (donor_group → recipient_group) | composite PK; generated from the ABO + Rh rules so it's always complete |

**Indexes:** `donations(donor_id)`, a partial FEFO index `blood_units(blood_group, expiry_date) WHERE status='Available'`, `blood_units(status, expiry_date)`, `blood_requests(hospital_id)`, `blood_requests(status)`, `blood_issues(request_id)`.

## Rules enforced inside the database

| # | Rule | Object |
|---|---|---|
| 1 | Donor must be 18–65, ≥ 45 kg, hemoglobin ≥ 12.5, and ≥ 90 days since last donation, otherwise `RAISE EXCEPTION` with the reason | trigger `trg_donations_eligibility` (BEFORE INSERT on donations) |
| 2 | Each donation automatically creates a blood unit expiring 35 days later and updates `donors.last_donation_date` | trigger `trg_donations_create_unit` (AFTER INSERT on donations) |
| 3 | Units past expiry become `Expired`, and expired units are never issuable | `mark_expired_units()`; also checked in `trg_issues_validate` |
| 4 | A unit can only be issued to a compatible request, and only while Available | trigger `trg_issues_validate` (BEFORE INSERT on blood_issues). This also blocks manual INSERTs typed into pgAdmin |
| 5 | FEFO issuing: exact group first, then earliest expiry; locks rows with `FOR UPDATE SKIP LOCKED`; updates request status; one transaction | `issue_blood(request_id)` |
| 6 | Reporting views | `v_stock_summary`, `v_near_expiry`, `v_request_status`, plus `v_donor_eligibility` |

## Seed data (what makes the demo work)

* **15 donors**, covering all 8 groups. Three of them can never donate as they are: **Kavita Rao** (hemoglobin 11.4), **Rohan Mehta** (age 17) and **Ananya Iyer** (44 kg). Everyone who donated within the last 90 days, such as **Aarav Sharma**, is also blocked for now. **Karan Malhotra** (AB+) and **Divya Menon** (AB-) are eligible today.
* **12 donations, so 12 units.** Sanjay's O- unit expired 5 days ago but is still marked *Available* until you click "Mark expired units". Two older units have been expired for a long time. Three units expire within 7 days: AB+ in 3 days, A+ in 5, B+ in 6.
* **5 hospitals** and **3 pending requests:**
  * Request 1, Ramesh Patil, **A+ × 2**: two exact matches, so FEFO takes the one expiring in 5 days first, then the one expiring in 25 days.
  * Request 2, Fatima Shaikh, **O- × 2**: one O- unit has expired and is skipped, so only one unit is issued and the request becomes **Partially Fulfilled**.
  * Request 3, George Thomas, **B+ × 3**: both B+ units are issued first because exact matches come first. The third is the compatible unit with the earliest expiry, which is the **B-** unit, chosen ahead of O+ and O-.

## Demo script (pgAdmin → bloodbank → Query Tool)

Tip: start with `BEGIN;` and finish with `ROLLBACK;`. The demo then leaves the data unchanged, and you can run it again.

**1. Python ↔ PostgreSQL connectivity** (run this while `app.py` is open)
```sql
SELECT pid, application_name, usename, client_addr, backend_start, state
FROM pg_stat_activity WHERE datname = 'bloodbank';
```

**2. The data and the views**
```sql
SELECT * FROM v_donor_eligibility;   -- who can donate today, and why not
SELECT * FROM v_stock_summary;       -- available units per blood group
SELECT * FROM v_near_expiry;         -- Available units expiring within 7 days
SELECT * FROM v_request_status;      -- requests with issued / remaining counts
SELECT donor_group, string_agg(recipient_group, ', ' ORDER BY recipient_group) AS can_give_to
FROM blood_compatibility GROUP BY donor_group ORDER BY donor_group;
```

**3. Rule 1: an ineligible donor is rejected by the trigger**
```sql
INSERT INTO donations (donor_id) SELECT id FROM donors WHERE name = 'Kavita Rao';
-- ERROR: Donor Kavita Rao is not eligible: hemoglobin 11.4 g/dL is below the minimum of 12.5
INSERT INTO donations (donor_id) SELECT id FROM donors WHERE name = 'Aarav Sharma';
-- ERROR: ... last donated on ... must wait 90 days, next eligible on ...
```

**4. Rule 2: an eligible donation creates a unit automatically**
```sql
INSERT INTO donations (donor_id) SELECT id FROM donors WHERE name = 'Karan Malhotra';
SELECT u.*, u.expiry_date - u.collection_date AS shelf_days
FROM blood_units u ORDER BY u.id DESC LIMIT 1;                         -- shelf_days = 35
SELECT name, last_donation_date FROM donors WHERE name = 'Karan Malhotra';  -- today
```

**5. Rule 3: expiry**
```sql
SELECT id, blood_group, expiry_date, status FROM blood_units WHERE expiry_date < CURRENT_DATE;
SELECT mark_expired_units();          -- returns how many units were marked
SELECT id, blood_group, expiry_date, status FROM blood_units WHERE expiry_date < CURRENT_DATE;
```

**6. Rule 5: FEFO order proven.** First preview the order the rule should give, then compare it with what `issue_blood` actually issues.
```sql
-- what FEFO should pick for request 3 (B+ x3)
SELECT u.id, u.blood_group, u.expiry_date,
       (u.blood_group = r.blood_group_needed) AS exact_match
FROM blood_units u
JOIN blood_requests r ON r.id = 3
JOIN blood_compatibility c ON c.donor_group = u.blood_group
                          AND c.recipient_group = r.blood_group_needed
WHERE u.status = 'Available' AND u.expiry_date >= CURRENT_DATE
ORDER BY exact_match DESC, u.expiry_date, u.id;

SELECT * FROM issue_blood(3);         -- same first 3 rows: B+, B+, then B-
SELECT * FROM v_request_status;       -- request 3 = Fulfilled
SELECT * FROM issue_blood(2);         -- O- x2: expired unit skipped, 1 issued
SELECT * FROM v_request_status;       -- request 2 = Partially Fulfilled
```

**7. Rule 4: compatibility and double issue blocked, even for manual INSERTs**
```sql
-- AB+ unit to the O- request -> rejected
INSERT INTO blood_issues (request_id, unit_id)
SELECT 2, id FROM blood_units WHERE blood_group = 'AB+' AND status = 'Available' LIMIT 1;
-- an already-issued unit -> rejected
INSERT INTO blood_issues (request_id, unit_id)
SELECT 1, unit_id FROM blood_issues LIMIT 1;
```

**8. Row locking (optional, needs two Query Tool tabs)**
Tab A: `BEGIN; SELECT * FROM issue_blood(1);` (leave it uncommitted)
Tab B: `SELECT * FROM blood_units WHERE blood_group = 'A+' FOR UPDATE SKIP LOCKED;`
Tab B does not see the two A+ units that Tab A is holding. Finish Tab A with `ROLLBACK;`.

```sql
ROLLBACK;   -- if you started with BEGIN, the data is back to the seed state
```

## Resetting the data
`init_db.py` never drops anything. To return to a clean seed after demos you committed:

1. In pgAdmin, delete the `bloodbank` database (right-click → *Delete*).
2. Run `python init_db.py` again.

This permanently deletes all data in `bloodbank`.
