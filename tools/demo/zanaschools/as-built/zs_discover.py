"""ZanaSchools demo — read-only discovery. Changes nothing."""
import os, frappe

BENCH = "/home/frappe/frappe-bench"
SITES = os.path.join(BENCH, "sites")
os.chdir(SITES)
SITE = os.environ.get("ZS_SITE") or ""
if not SITE:
    cands = sorted(d for d in os.listdir(SITES)
                   if os.path.isfile(os.path.join(SITES, d, "site_config.json")))
    print("Sites on this bench:", cands)
    SITE = cands[0]
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()

def h(t): print("\n=== " + t + " ===")
def safe(fn):
    try: fn()
    except Exception as e: print("  (skipped:", repr(e)[:150], ")")

h("SITE / SYSTEM")
ss = frappe.get_single("System Settings")
print("site:", SITE, "| country:", ss.country, "| tz:", ss.time_zone,
      "| currency:", frappe.db.get_default("currency"), "| date_format:", ss.date_format)

h("INSTALLED APPS")
apps = frappe.get_installed_apps()
for app in apps:
    try: v = frappe.get_attr(app + ".__version__")
    except Exception: v = "?"
    print(f"  {app:25} {v}")

h("COMPANIES / FISCAL YEARS")
for c in frappe.get_all("Company", fields=["name", "abbr", "default_currency", "country"]):
    print("  ", dict(c))
safe(lambda: [print("  FY", dict(f)) for f in frappe.get_all(
    "Fiscal Year", fields=["name", "year_start_date", "year_end_date"])])

CORE = {"frappe", "erpnext", "hrms", "education", "payments", "lms", "insights"}
custom_apps = [a for a in apps if a not in CORE]
mods = frappe.get_all("Module Def", filters={"app_name": ["in", ["education"] + custom_apps]}, pluck="name")
dts = frappe.get_all("DocType", filters={"module": ["in", mods], "istable": 0},
                     fields=["name", "module", "issingle"], order_by="module, name")

h("RECORD COUNTS: Education + custom-app doctypes")
for d in dts:
    if d.issingle: continue
    try: n = frappe.db.count(d.name)
    except Exception as e: n = f"ERR {e}"
    print(f"  [{d.module}] {d.name}: {n}")

h("RECORD COUNTS: supporting doctypes")
for dt in ["Customer", "Item", "Sales Invoice", "Payment Entry", "Employee", "Department",
           "Designation", "Holiday List", "User", "Contact", "Event", "Web Page", "Blog Post"]:
    if frappe.db.exists("DocType", dt): print(f"  {dt}: {frappe.db.count(dt)}")

h("EDUCATION SETTINGS")
def _es():
    es = frappe.get_single("Education Settings").as_dict()
    for k, v in es.items():
        if k not in ("doctype", "name", "owner", "modified_by", "creation", "modified", "idx", "docstatus") \
                and v not in (None, "", 0, []):
            print(f"  {k}: {v}")
safe(_es)

h("SCHEMA: key doctypes (* = mandatory)")
KEY = ["Student", "Guardian", "Student Applicant", "Program", "Course", "Program Enrollment",
       "Course Enrollment", "Student Group", "Instructor", "Room", "Course Schedule",
       "Student Attendance", "Student Leave Application", "Assessment Plan", "Assessment Result",
       "Grading Scale", "Fee Structure", "Fee Schedule", "Fees", "Student Log"]
for dt in KEY:
    if not frappe.db.exists("DocType", dt):
        print(f"\n  {dt}: (not present)"); continue
    meta = frappe.get_meta(dt)
    print(f"\n  {dt}  [submittable={meta.is_submittable}, autoname={meta.autoname}]")
    for f in meta.fields:
        if f.reqd or f.fieldtype in ("Link", "Table", "Select", "Dynamic Link"):
            opt = (f.options or "").replace("\n", "|")[:70]
            print(f"    {'*' if f.reqd else ' '} {f.fieldname} ({f.fieldtype}) {opt}")

h("CUSTOM FIELDS on these doctypes")
safe(lambda: [print(f"  {cf.dt}.{cf.fieldname} ({cf.fieldtype}) {cf.options or ''} {'REQD' if cf.reqd else ''}")
              for cf in frappe.get_all("Custom Field", filters={"dt": ["in", [d.name for d in dts] + KEY]},
                                       fields=["dt", "fieldname", "fieldtype", "options", "reqd"], order_by="dt")])

h("ROLES & PORTAL")
for r in ["Student", "Guardian", "Instructor", "Academics User", "Education Manager", "Accounts User"]:
    if frappe.db.exists("Role", r):
        print(f"  role {r}: {frappe.db.count('Has Role', {'role': r, 'parenttype': 'User'})} users")
safe(lambda: print("  portal menu:", [m.title for m in frappe.get_single("Portal Settings").menu if m.enabled]))
for app in custom_apps:
    www = frappe.get_app_path(app, "www")
    if os.path.isdir(www): print(f"  {app} www:", sorted(os.listdir(www)))

h("SAMPLE EXISTING MASTER DATA")
for dt, flds in [("Academic Year", ["name", "year_start_date", "year_end_date"]),
                 ("Academic Term", ["name", "academic_year", "term_start_date", "term_end_date"]),
                 ("Program", ["name"]), ("Course", ["name"]), ("Student Category", ["name"]),
                 ("Student Batch Name", ["name"]), ("Assessment Group", ["name", "parent_assessment_group"]),
                 ("Assessment Criteria", ["name"]), ("Grading Scale", ["name"]),
                 ("Fee Category", ["name"]), ("Room", ["name"]), ("School House", ["name"])]:
    if frappe.db.exists("DocType", dt):
        safe(lambda dt=dt, flds=flds: print(f"  {dt} ({frappe.db.count(dt)}):",
             [tuple(r.values()) for r in frappe.get_all(dt, fields=flds, limit=15)]))

frappe.destroy()
print("\nDONE")
