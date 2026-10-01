"""
ZanaSchools demo - Phase 1: clean-up + foundation.
Dry run by default. Set ZS_APPLY=1 to write.
"""
import os, frappe

SITE = "zanaschools-demo.zanaverse.com"
SITES = "/home/frappe/frappe-bench/sites"
APPLY = os.environ.get("ZS_APPLY") == "1"

COMPANY = "Zana International School"
ABBR = "ZIS"
CURRENCY = "USD"
COUNTRY = "Nigeria"          # campus location; drives chart of accounts localisation only

FISCAL_YEARS = [("2026-2027", "2026-04-01", "2027-03-31")]  # 2025-2026 already exists
ACADEMIC_YEARS = {
    "2025-2026": ("2025-09-01", "2026-08-31", []),  # exists; terms exist
    "2026-2027": ("2026-09-01", "2027-08-31", [
        ("Term 1", "2026-09-07", "2026-12-11"),
        ("Term 2", "2027-01-11", "2027-04-01"),
        ("Term 3", "2027-04-26", "2027-07-16"),
    ]),
}

# transactional test data, children before parents
PURGE_ORDER = ["Payment Entry", "Fees", "Fee Schedule", "Fee Structure",
               "Assessment Result", "Assessment Plan", "Student Attendance",
               "Student Leave Application", "Student Log", "Course Schedule",
               "Course Enrollment", "Program Enrollment", "Student Group",
               "Student", "Guardian"]

def is_test_user(u):
    return (u.endswith("@student.demo") or u.endswith("@gmail.com")
            or u == "jane.mwangi@email.com")

os.chdir(SITES)
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()
frappe.set_user("Administrator")
print(f"MODE: {'APPLY' if APPLY else 'DRY RUN (nothing written)'}\n")

errors = []

# ---------- 1. purge ----------
print("== 1. Purge old test transactions ==")
if APPLY:
    frappe.db.set_single_value("Accounts Settings", "delete_linked_ledger_entries", 1)
for dt in PURGE_ORDER:
    if not frappe.db.exists("DocType", dt):
        continue
    names = frappe.get_all(dt, pluck="name", order_by="creation desc")
    print(f"  {dt}: {len(names)}")
    if not APPLY:
        continue
    for n in names:
        try:
            d = frappe.get_doc(dt, n)
            if d.docstatus == 1:
                d.flags.ignore_links = True
                d.flags.ignore_permissions = True
                d.cancel()
            frappe.delete_doc(dt, n, force=1, ignore_permissions=True, delete_permanently=True)
        except Exception as e:
            errors.append(f"{dt} {n}: {repr(e)[:160]}")
            frappe.db.rollback()
        else:
            frappe.db.commit()

# ---------- 2. disable test / personal users ----------
print("\n== 2. Disable test & personal-email users ==")
for u in frappe.get_all("User", filters={"enabled": 1}, pluck="name"):
    if is_test_user(u):
        print(f"  disable {u}")
        if APPLY:
            frappe.db.set_value("User", u, "enabled", 0)
if APPLY: frappe.db.commit()

# ---------- 3. company ----------
print(f"\n== 3. Company: {COMPANY} ({CURRENCY}) ==")
if frappe.db.exists("Company", COMPANY):
    print("  exists")
elif APPLY:
    try:
        c = frappe.get_doc({
            "doctype": "Company", "company_name": COMPANY, "abbr": ABBR,
            "default_currency": CURRENCY, "country": COUNTRY,
            "create_chart_of_accounts_based_on": "Standard Template",
            "chart_of_accounts": "Standard",
        })
        c.insert(ignore_permissions=True)
        frappe.db.commit()
        print("  created")
    except Exception as e:
        errors.append(f"Company: {repr(e)[:300]}"); frappe.db.rollback()
else:
    print("  would create")

if APPLY and frappe.db.exists("Company", COMPANY):
    gd = frappe.get_single("Global Defaults")
    gd.default_company = COMPANY
    gd.default_currency = CURRENCY
    gd.save(ignore_permissions=True)
    frappe.db.set_default("company", COMPANY)
    frappe.db.commit()
    print("  set as default company")

# ---------- 4. fiscal years ----------
print("\n== 4. Fiscal years ==")
for name, s, e in FISCAL_YEARS:
    if frappe.db.exists("Fiscal Year", name):
        print(f"  {name} exists")
    elif APPLY:
        try:
            frappe.get_doc({"doctype": "Fiscal Year", "year": name,
                            "year_start_date": s, "year_end_date": e}).insert(ignore_permissions=True)
            frappe.db.commit(); print(f"  {name} created")
        except Exception as ex:
            errors.append(f"Fiscal Year {name}: {repr(ex)[:200]}"); frappe.db.rollback()
    else:
        print(f"  would create {name} ({s} -> {e})")

# ---------- 5. academic years & terms ----------
print("\n== 5. Academic years & terms ==")
for ay, (s, e, terms) in ACADEMIC_YEARS.items():
    if not frappe.db.exists("Academic Year", ay):
        if APPLY:
            frappe.get_doc({"doctype": "Academic Year", "academic_year_name": ay,
                            "year_start_date": s, "year_end_date": e}).insert(ignore_permissions=True)
        print(f"  {'created' if APPLY else 'would create'} {ay}")
    else:
        print(f"  {ay} exists")
    for tn, ts, te in terms:
        full = f"{ay} ({tn})"
        if frappe.db.exists("Academic Term", full):
            print(f"    {full} exists"); continue
        if APPLY:
            try:
                frappe.get_doc({"doctype": "Academic Term", "academic_year": ay, "term_name": tn,
                                "term_start_date": ts, "term_end_date": te}).insert(ignore_permissions=True)
            except Exception as ex:
                errors.append(f"Term {full}: {repr(ex)[:200]}"); frappe.db.rollback(); continue
        print(f"    {'created' if APPLY else 'would create'} {full} ({ts} -> {te})")
if APPLY: frappe.db.commit()

# ---------- 6. education settings ----------
print("\n== 6. Education Settings: current year/term ==")
if APPLY and frappe.db.exists("Academic Term", "2026-2027 (Term 1)"):
    frappe.db.set_single_value("Education Settings", "current_academic_year", "2026-2027")
    frappe.db.set_single_value("Education Settings", "current_academic_term", "2026-2027 (Term 1)")
    frappe.db.commit()
    print("  set to 2026-2027 / Term 1")
else:
    print("  would set to 2026-2027 / Term 1")

# ---------- verify ----------
print("\n== VERIFY ==")
for dt in PURGE_ORDER:
    if frappe.db.exists("DocType", dt):
        n = frappe.db.count(dt)
        if n: print(f"  {dt} remaining: {n}")
print("  companies:", frappe.get_all("Company", fields=["name", "default_currency"]))
print("  default company:", frappe.db.get_default("company"))
print("  fiscal years:", frappe.get_all("Fiscal Year", pluck="name"))
print("  terms:", frappe.get_all("Academic Term", pluck="name", order_by="term_start_date"))
print("  enabled users:", frappe.db.count("User", {"enabled": 1}))

print("\nERRORS:" if errors else "\nNo errors.")
for x in errors: print("  ", x)
frappe.destroy()
