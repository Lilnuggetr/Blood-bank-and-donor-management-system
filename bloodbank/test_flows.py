import sys

import psycopg2

import db

results = []

def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"\n       {detail}" if detail else ""))

def expect_error(cur, name, sql, params):
    cur.execute("SAVEPOINT t")
    try:
        cur.execute(sql, params)
    except psycopg2.Error as exc:
        cur.execute("ROLLBACK TO SAVEPOINT t")
        check(name, True, "DB said: " + db.error_message(exc))
        return
    cur.execute("ROLLBACK TO SAVEPOINT t")
    check(name, False, "statement was accepted but should have been rejected")

def one(cur, sql, params=None):
    cur.execute(sql, params)
    return cur.fetchone()

def donor_id(cur, name):
    return one(cur, "SELECT id FROM donors WHERE name = %s", (name,))[0]

def request_id(cur, patient):
    return one(cur, "SELECT id FROM blood_requests WHERE patient_name = %s", (patient,))[0]

def fefo_candidates(cur, req_id):
    cur.execute("""
        SELECT u.id, u.blood_group, u.expiry_date
          FROM blood_units u
          JOIN blood_requests r ON r.id = %s
          JOIN blood_compatibility c
            ON c.donor_group = u.blood_group AND c.recipient_group = r.blood_group_needed
         WHERE u.status = 'Available' AND u.expiry_date >= CURRENT_DATE
         ORDER BY (u.blood_group = r.blood_group_needed) DESC, u.expiry_date, u.id
         LIMIT (SELECT units_needed FROM blood_requests WHERE id = %s)""", (req_id, req_id))
    return cur.fetchall()

def main():
    conn = db.connect()
    cur = conn.cursor()
    print(f"Connected to {db.DB_NAME} @ {db.DB_HOST}:{db.DB_PORT}\n")
    insert_donation = "INSERT INTO donations (donor_id, donation_date, volume_ml) VALUES (%s, CURRENT_DATE, 450)"

    try:
        for name, reason in [("Kavita Rao", "low hemoglobin"), ("Rohan Mehta", "under 18"),
                             ("Ananya Iyer", "under 45 kg"), ("Aarav Sharma", "donated < 90 days ago")]:
            expect_error(cur, f"Ineligible donation rejected ({name}, {reason})",
                         insert_donation, (donor_id(cur, name),))

        did = donor_id(cur, "Karan Malhotra")
        cur.execute(insert_donation + " RETURNING id", (did,))
        donation = cur.fetchone()[0]
        unit = one(cur, "SELECT id, blood_group, collection_date, expiry_date, status, "
                        "expiry_date - collection_date FROM blood_units WHERE donation_id = %s", (donation,))
        last = one(cur, "SELECT last_donation_date = CURRENT_DATE FROM donors WHERE id = %s", (did,))[0]
        check("Eligible donation (Karan Malhotra) creates a blood unit",
              unit is not None and unit[5] == 35 and unit[4] == "Available" and last,
              f"donation {donation} -> unit {unit[0]} {unit[1]}, collected {unit[2]}, "
              f"expires {unit[3]} (+{unit[5]} days), status {unit[4]}; last_donation_date updated: {last}")

        r1 = request_id(cur, "Ramesh Patil")
        expected = fefo_candidates(cur, r1)
        cur.execute("SELECT * FROM issue_blood(%s)", (r1,))
        issued = cur.fetchall()
        status = one(cur, "SELECT status FROM blood_requests WHERE id = %s", (r1,))[0]
        check("FEFO issue for A+ x2 picks earliest-expiry compatible units",
              [u[0] for u in issued] == [u[0] for u in expected] and status == "Fulfilled",
              "issued " + ", ".join(f"unit {u[0]} {u[1]} exp {u[2]}" for u in issued) + f" -> {status}")

        r2 = request_id(cur, "Fatima Shaikh")
        expired = one(cur, "SELECT id, expiry_date FROM blood_units WHERE blood_group = 'O-' "
                           "AND expiry_date < CURRENT_DATE ORDER BY expiry_date LIMIT 1")
        cur.execute("SELECT * FROM issue_blood(%s)", (r2,))
        issued = cur.fetchall()
        status = one(cur, "SELECT status FROM blood_requests WHERE id = %s", (r2,))[0]
        exp_status = one(cur, "SELECT status FROM blood_units WHERE id = %s", (expired[0],))[0]
        check("Expired O- unit is skipped; request becomes Partially Fulfilled",
              expired[0] not in [u[0] for u in issued] and status == "Partially Fulfilled"
              and exp_status == "Expired",
              f"expired unit {expired[0]} (exp {expired[1]}) now '{exp_status}'; issued "
              + ", ".join(f"unit {u[0]} {u[1]} exp {u[2]}" for u in issued) + f" -> {status}")

        r3 = request_id(cur, "George Thomas")
        cur.execute("SELECT * FROM issue_blood(%s)", (r3,))
        issued = cur.fetchall()
        groups = [u[1] for u in issued]
        check("B+ x3: both B+ units first, then nearest-expiry compatible (B-)",
              groups == ["B+", "B+", "B-"] and issued[0][2] <= issued[1][2],
              "issued " + ", ".join(f"unit {u[0]} {u[1]} exp {u[2]}" for u in issued))

        ab_unit = one(cur, "SELECT id FROM blood_units WHERE blood_group = 'AB+' AND status = 'Available' LIMIT 1")[0]
        expect_error(cur, "Incompatible manual issue (AB+ unit -> O- request) rejected",
                     "INSERT INTO blood_issues (request_id, unit_id) VALUES (%s, %s)", (r2, ab_unit))

        expect_error(cur, "Issuing an already-issued unit again is rejected",
                     "INSERT INTO blood_issues (request_id, unit_id) VALUES (%s, %s)", (r3, issued[0][0]))

        expect_error(cur, "Manual issue of an expired unit rejected",
                     "INSERT INTO blood_issues (request_id, unit_id) VALUES (%s, %s)", (r2, expired[0]))

        expect_error(cur, "issue_blood on an already Fulfilled request rejected",
                     "SELECT * FROM issue_blood(%s)", (r1,))
    finally:
        conn.rollback()
        conn.close()
        print("\nRolled back - seed data unchanged.")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return all(results)

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
