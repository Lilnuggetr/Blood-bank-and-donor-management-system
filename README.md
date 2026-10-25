# Blood Bank & Donor Management System

A DBMS mini project: a Tkinter desktop app (Python + psycopg2) on PostgreSQL 16.

Manual blood bank tracking lets donors give blood too early, lets expired units slip through, and issues blood without checking compatibility. This project keeps donors, donations, blood units and hospital requests in one database. **The database itself** enforces donor eligibility, expiry and ABO/Rh compatibility, and issues blood **First-Expiry-First-Out (FEFO)** to reduce wastage. The Python app only calls the database and shows its results and error messages.

## Features

- Donor, donation, stock and hospital-request management in a Tkinter UI
- Eligibility checks by trigger: age 18-65, weight of at least 45 kg, hemoglobin of at least 12.5 g/dL, and 90 days since the last donation
- Each donation automatically creates a blood unit that expires after 35 days
- Expired units are never issuable
- Compatibility-checked, FEFO issuing through `issue_blood(request_id)`, with row locking
- Reporting views: stock summary, near-expiry units, request status and donor eligibility
- Tables are in 3NF, with constraints and indexes

## Repository layout

| Path | Contents |
|---|---|
| `bloodbank/` | The application: `app.py` (UI), `db.py`, `init_db.py`, `test_flows.py` and `sql/` (schema, logic, seed data) |
| `pg-docker/` | Optional Docker Compose setup for PostgreSQL 16 and pgAdmin |

## Quick start

You need Python 3 and a PostgreSQL server (version 13 or newer). Either install PostgreSQL locally or use the Docker setup in `pg-docker/`.

1. Create `bloodbank/.env` with your own PostgreSQL credentials. This file is gitignored and is not in the repo.
   ```
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password_here
   ```
   Add `DB_PORT=5433` (for example) if your server isn't on port 5432.
2. Install the dependencies and set up the database:
   ```powershell
   cd bloodbank
   pip install -r requirements.txt
   python init_db.py      # creates the `bloodbank` database, runs the SQL files, adds seed data
   ```
3. Run the app:
   ```powershell
   python app.py
   ```
4. Optional: run the 12 automated rule checks, which are rolled back afterwards:
   ```powershell
   python test_flows.py
   ```

To use Docker instead, create `pg-docker/.env` (also gitignored) with the `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` values, then run `docker compose up -d` in that folder. pgAdmin is then at http://localhost:5050.

`init_db.py` is safe to re-run. It only creates what is missing and never drops anything.

## More detail

[bloodbank/README.md](bloodbank/README.md) covers the table design, every database rule, the seed data and a step-by-step pgAdmin demo script.
