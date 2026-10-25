import datetime
import tkinter as tk
from tkinter import messagebox, ttk

import db

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
STATUS_REFRESH_MS = 5000

def make_tree(parent, columns, height=10):
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=110, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return frame, tree

def fill_tree(tree, rows):
    tree.delete(*tree.get_children())
    for row in rows:
        tree.insert("", "end", values=["" if v is None else str(v) for v in row])

def blank_to_none(value):
    value = value.strip()
    return value or None

def id_from_choice(choice):
    return int(choice.split(" - ", 1)[0]) if choice else None

class App:
    def __init__(self, root):
        self.root = root
        root.title("Blood Bank & Donor Management System")
        root.geometry("1050x620")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.status = tk.StringVar(value="Connecting...")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

        self.refreshers = {}
        self.build_donors_tab()
        self.build_donations_tab()
        self.build_stock_tab()
        self.build_requests_tab()
        self.build_issue_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.update_status()

    def add_tab(self, title, refresh):
        frame = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(frame, text=title)
        self.refreshers[str(frame)] = refresh
        return frame

    def run(self, sql, params=None):
        try:
            return db.query(sql, params)
        except Exception as exc:
            self.update_status(schedule=False)
            messagebox.showerror("Database error", db.error_message(exc))
            return None

    def rows(self, sql, params=None):
        result = self.run(sql, params)
        return result[1] if result else []

    def on_tab_changed(self, _event):
        refresh = self.refreshers.get(self.notebook.select())
        if refresh:
            refresh()

    def update_status(self, schedule=True):
        _, text = db.connection_status()
        self.status.set(text)
        if schedule:
            self.root.after(STATUS_REFRESH_MS, self.update_status)

    @staticmethod
    def form_row(parent, row, label, widget):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
        widget.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        return widget

    def build_donors_tab(self):
        tab = self.add_tab("Donors", self.refresh_donors)
        form = ttk.LabelFrame(tab, text="Add donor", padding=6)
        form.pack(fill="x")

        self.d_name = self.form_row(form, 0, "Name", ttk.Entry(form, width=30))
        self.d_dob = self.form_row(form, 1, "Date of birth (YYYY-MM-DD)", ttk.Entry(form, width=15))
        self.d_gender = self.form_row(form, 2, "Gender", ttk.Combobox(
            form, values=["Male", "Female", "Other"], state="readonly", width=12))
        self.d_phone = self.form_row(form, 3, "Phone", ttk.Entry(form, width=15))
        self.d_group = self.form_row(form, 4, "Blood group", ttk.Combobox(
            form, values=BLOOD_GROUPS, state="readonly", width=6))
        self.d_weight = self.form_row(form, 5, "Weight (kg)", ttk.Entry(form, width=8))
        self.d_hb = self.form_row(form, 6, "Hemoglobin (g/dL)", ttk.Entry(form, width=8))
        ttk.Button(form, text="Add donor", command=self.add_donor).grid(row=7, column=1, sticky="w", padx=4, pady=4)

        ttk.Button(tab, text="Refresh", command=self.refresh_donors).pack(anchor="w", pady=(8, 2))
        frame, self.donors_tree = make_tree(tab, ("id", "name", "blood_group", "age", "weight_kg",
                                                  "hemoglobin", "last_donation", "eligible_today"))
        self.donors_tree.column("eligible_today", width=230)
        frame.pack(fill="both", expand=True)

    def add_donor(self):
        params = (blank_to_none(self.d_name.get()), blank_to_none(self.d_dob.get()),
                  blank_to_none(self.d_gender.get()), blank_to_none(self.d_phone.get()),
                  blank_to_none(self.d_group.get()), blank_to_none(self.d_weight.get()),
                  blank_to_none(self.d_hb.get()))
        result = self.run("INSERT INTO donors (name, dob, gender, phone, blood_group, weight_kg, hemoglobin) "
                          "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id", params)
        if result:
            messagebox.showinfo("Donor added", f"Donor saved with id {result[1][0][0]}")
            for entry in (self.d_name, self.d_dob, self.d_phone, self.d_weight, self.d_hb):
                entry.delete(0, "end")
            self.refresh_donors()

    def refresh_donors(self):
        fill_tree(self.donors_tree, self.rows(
            "SELECT id, name, blood_group, age, weight_kg, hemoglobin, last_donation_date, eligible "
            "FROM v_donor_eligibility ORDER BY id"))

    def build_donations_tab(self):
        tab = self.add_tab("Donations", self.refresh_donations)
        form = ttk.LabelFrame(tab, text="Record donation", padding=6)
        form.pack(fill="x")

        self.dn_donor = self.form_row(form, 0, "Donor", ttk.Combobox(form, state="readonly", width=40))
        self.dn_date = self.form_row(form, 1, "Donation date (YYYY-MM-DD)", ttk.Entry(form, width=15))
        self.dn_volume = self.form_row(form, 2, "Volume (ml)", ttk.Entry(form, width=8))
        self.dn_date.insert(0, datetime.date.today().isoformat())
        self.dn_volume.insert(0, "450")
        ttk.Button(form, text="Record donation", command=self.record_donation).grid(
            row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(tab, text="Donations and the blood unit each one created (by trigger):").pack(anchor="w", pady=(8, 2))
        frame, self.donations_tree = make_tree(tab, ("donation_id", "donor", "donation_date", "volume_ml",
                                                     "unit_id", "blood_group", "expiry_date", "unit_status"))
        frame.pack(fill="both", expand=True)

    def record_donation(self):
        donor = id_from_choice(self.dn_donor.get())
        if donor is None:
            messagebox.showwarning("Missing donor", "Choose a donor first")
            return
        result = self.run("INSERT INTO donations (donor_id, donation_date, volume_ml) "
                          "VALUES (%s, %s, %s) RETURNING id",
                          (donor, blank_to_none(self.dn_date.get()), blank_to_none(self.dn_volume.get())))
        if not result:
            return
        donation_id = result[1][0][0]
        unit = self.rows("SELECT id, blood_group, expiry_date FROM blood_units WHERE donation_id = %s",
                         (donation_id,))
        if unit:
            uid, group, expiry = unit[0]
            messagebox.showinfo("Donation recorded",
                                f"Donation {donation_id} recorded.\nBlood unit {uid} ({group}) created, expires {expiry}.")
        self.refresh_donations()

    def refresh_donations(self):
        donors = self.rows("SELECT id, name, blood_group FROM donors ORDER BY name")
        self.dn_donor["values"] = [f"{i} - {n} ({g})" for i, n, g in donors]
        fill_tree(self.donations_tree, self.rows(
            "SELECT dn.id, d.name, dn.donation_date, dn.volume_ml, u.id, u.blood_group, u.expiry_date, u.status "
            "FROM donations dn JOIN donors d ON d.id = dn.donor_id "
            "LEFT JOIN blood_units u ON u.donation_id = dn.id ORDER BY dn.id DESC"))

    def build_stock_tab(self):
        tab = self.add_tab("Stock", self.refresh_stock)
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Refresh", command=self.refresh_stock).pack(side="left")
        ttk.Button(buttons, text="Mark expired units", command=self.mark_expired).pack(side="left", padx=6)

        top = ttk.Frame(tab)
        top.pack(fill="x", pady=6)
        left = ttk.LabelFrame(top, text="Stock summary (v_stock_summary)", padding=4)
        left.pack(side="left", fill="both", padx=(0, 6))
        frame, self.stock_tree = make_tree(left, ("blood_group", "available_units"), height=8)
        frame.pack(fill="both")
        right = ttk.LabelFrame(top, text="Expiring within 7 days (v_near_expiry)", padding=4)
        right.pack(side="left", fill="both", expand=True)
        frame, self.near_tree = make_tree(right, ("unit_id", "blood_group", "collection_date",
                                                  "expiry_date", "days_left"), height=8)
        frame.pack(fill="both", expand=True)

        bottom = ttk.LabelFrame(tab, text="All blood units", padding=4)
        bottom.pack(fill="both", expand=True)
        frame, self.units_tree = make_tree(bottom, ("unit_id", "donation_id", "blood_group",
                                                    "collection_date", "expiry_date", "status"))
        frame.pack(fill="both", expand=True)

    def mark_expired(self):
        rows = self.rows("SELECT mark_expired_units()")
        if rows:
            messagebox.showinfo("Expiry check", f"{rows[0][0]} unit(s) marked as Expired")
        self.refresh_stock()

    def refresh_stock(self):
        fill_tree(self.stock_tree, self.rows("SELECT blood_group, available_units FROM v_stock_summary"))
        fill_tree(self.near_tree, self.rows(
            "SELECT unit_id, blood_group, collection_date, expiry_date, days_left FROM v_near_expiry"))
        fill_tree(self.units_tree, self.rows(
            "SELECT id, donation_id, blood_group, collection_date, expiry_date, status "
            "FROM blood_units ORDER BY expiry_date, id"))

    def build_requests_tab(self):
        tab = self.add_tab("Requests", self.refresh_requests)
        form = ttk.LabelFrame(tab, text="New hospital request", padding=6)
        form.pack(fill="x")

        self.r_hospital = self.form_row(form, 0, "Hospital", ttk.Combobox(form, state="readonly", width=40))
        self.r_patient = self.form_row(form, 1, "Patient name", ttk.Entry(form, width=30))
        self.r_group = self.form_row(form, 2, "Blood group needed", ttk.Combobox(
            form, values=BLOOD_GROUPS, state="readonly", width=6))
        self.r_units = self.form_row(form, 3, "Units needed", ttk.Entry(form, width=8))
        ttk.Button(form, text="Add request", command=self.add_request).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        ttk.Button(tab, text="Refresh", command=self.refresh_requests).pack(anchor="w", pady=(8, 2))
        frame, self.requests_tree = make_tree(tab, ("request_id", "hospital", "patient", "group_needed",
                                                    "units_needed", "units_issued", "remaining",
                                                    "request_date", "status"))
        self.requests_tree.column("hospital", width=180)
        frame.pack(fill="both", expand=True)

    def add_request(self):
        hospital = id_from_choice(self.r_hospital.get())
        result = self.run("INSERT INTO blood_requests (hospital_id, patient_name, blood_group_needed, units_needed) "
                          "VALUES (%s, %s, %s, %s) RETURNING id",
                          (hospital, blank_to_none(self.r_patient.get()),
                           blank_to_none(self.r_group.get()), blank_to_none(self.r_units.get())))
        if result:
            messagebox.showinfo("Request added", f"Request saved with id {result[1][0][0]}")
            self.r_patient.delete(0, "end")
            self.r_units.delete(0, "end")
            self.refresh_requests()

    def refresh_requests(self):
        hospitals = self.rows("SELECT id, name, city FROM hospitals ORDER BY name")
        self.r_hospital["values"] = [f"{i} - {n} ({c})" for i, n, c in hospitals]
        fill_tree(self.requests_tree, self.rows(
            "SELECT request_id, hospital, patient_name, blood_group_needed, units_needed, "
            "units_issued, units_remaining, request_date, status FROM v_request_status"))

    def build_issue_tab(self):
        tab = self.add_tab("Issue Blood", self.refresh_issue)
        ttk.Label(tab, text="Open requests (Pending / Partially Fulfilled) - select one:").pack(anchor="w")
        frame, self.open_tree = make_tree(tab, ("request_id", "hospital", "patient", "group_needed",
                                                "units_needed", "units_issued", "remaining", "status"), height=8)
        self.open_tree.column("hospital", width=180)
        frame.pack(fill="both", expand=True)

        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=6)
        ttk.Button(buttons, text="Issue (FEFO)", command=self.issue).pack(side="left")
        ttk.Button(buttons, text="Refresh", command=self.refresh_issue).pack(side="left", padx=6)

        self.issue_label = tk.StringVar(value="Units issued by the last issue_blood() call:")
        ttk.Label(tab, textvariable=self.issue_label).pack(anchor="w")
        frame, self.issued_tree = make_tree(tab, ("unit_id", "blood_group", "expiry_date"), height=6)
        frame.pack(fill="both", expand=True)

    def issue(self):
        selected = self.open_tree.selection()
        if not selected:
            messagebox.showwarning("No request", "Select a request first")
            return
        request_id = int(self.open_tree.item(selected[0], "values")[0])
        result = self.run("SELECT unit_id, blood_group, expiry_date FROM issue_blood(%s)", (request_id,))
        if result is None:
            return
        issued = result[1]
        fill_tree(self.issued_tree, issued)
        status = self.rows("SELECT status FROM blood_requests WHERE id = %s", (request_id,))
        status = status[0][0] if status else "?"
        self.issue_label.set(f"Request {request_id}: issued {len(issued)} unit(s) - request is now {status}")
        if not issued:
            messagebox.showinfo("Nothing issued", f"No compatible, unexpired units available for request {request_id}")
        self.refresh_issue()

    def refresh_issue(self):
        fill_tree(self.open_tree, self.rows(
            "SELECT request_id, hospital, patient_name, blood_group_needed, units_needed, units_issued, "
            "units_remaining, status FROM v_request_status WHERE status <> 'Fulfilled'"))

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
