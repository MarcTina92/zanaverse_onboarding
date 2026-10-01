"""
ZanaSchools demo - fix: departments + instructor teaching logs.
Dry run by default; ZS_APPLY=1 to write. Safe to re-run (logs are rebuilt each time).
"""
import os
from collections import defaultdict
import frappe

SITE = "zanaschools-demo.zanaverse.com"
SITES = "/home/frappe/frappe-bench/sites"
APPLY = os.environ.get("ZS_APPLY") == "1"
COMPANY = "Zana International School"
AY_PREV, AY_CUR = "2025-2026", "2026-2027"
CUR_TERM = "2026-2027 (Term 1)"
DEPTS = {
    "Primary": ["Esi Boateng", "Mutale Banda", "Olumide Adebayo", "Wanjiku Kamau"],
    "Mathematics": ["Ifeanyi Nwosu", "Kwame Asante"],
    "Sciences": ["Akinyi Ochieng", "Kojo Mensah", "Chanda Mulenga"],
    "Languages": ["Naledi Khumalo", "Baraka Otieno", "Aminata Sow"],
    "Humanities": ["Nakato Nsubuga", "Ilunga Kasongo", "Zainab Abubakar"],
    "Technology & Arts": ["Lwazi Dlamini", "Chileshe Phiri", "Collins Wanjala"],
    "Senior Leadership": ["Adaeze Okonkwo"],
    "Finance & Administration": ["Thabo Molefe", "Fatou Ndiaye"],
}

os.chdir(SITES)
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()
frappe.set_user("Administrator")
print(f"MODE: {'APPLY' if APPLY else 'DRY RUN (nothing written)'}\n")
abbr = frappe.db.get_value("Company", COMPANY, "abbr")
root = "All Departments" if frappe.db.exists("Department", "All Departments") else None
dept_of = {p: d for d, people in DEPTS.items() for p in people}

# this term: straight from the timetable
cur = frappe.db.sql("""select instructor_name, program, course, student_group from `tabCourse Schedule`
    where instructor_name is not null group by instructor_name, program, course, student_group""", as_dict=True)
logs = defaultdict(list)
teacher_of = {}
for r in cur:
    logs[r.instructor_name].append((AY_CUR, CUR_TERM, r.program, r.course, r.student_group))
    teacher_of[(r.program, r.course)] = r.instructor_name
# last year: same teacher for the same subject and year group, per class assessed last year
prev = frappe.db.sql("""select distinct program, course, student_group from `tabAssessment Plan`
    where academic_year=%s and docstatus=1""", AY_PREV, as_dict=True)
unmatched = 0
for r in prev:
    t = teacher_of.get((r.program, r.course))
    if t: logs[t].append((AY_PREV, None, r.program, r.course, r.student_group))
    else: unmatched += 1

print("== PLAN ==")
print(f"  departments to ensure: {len(DEPTS)} (root: {root})")
for name in sorted(dept_of):
    if name in {i for i in frappe.get_all("Instructor", pluck="instructor_name")}:
        print(f"  {name:18} {dept_of[name]:20} log rows: {len(logs.get(name, []))}")
print(f"  last-year classes with no matching teacher: {unmatched}")
if not APPLY:
    frappe.destroy(); print("\nDry run complete."); raise SystemExit

errors = []
dept_name = {}
for d in DEPTS:
    full = f"{d} - {abbr}"
    if not frappe.db.exists("Department", full):
        try:
            doc = frappe.get_doc({"doctype": "Department", "department_name": d, "company": COMPANY,
                                  "parent_department": root})
            doc.flags.ignore_permissions = True; doc.insert(); full = doc.name; frappe.db.commit()
        except Exception as e:
            frappe.db.rollback(); errors.append(f"Department {d}: {repr(e)[:200]}"); continue
    dept_name[d] = full

for person, d in dept_of.items():
    dn = dept_name.get(d)
    if not dn: continue
    first, last = person.split(" ", 1)
    emp = frappe.db.get_value("Employee", {"first_name": first, "last_name": last, "company": COMPANY})
    if emp: frappe.db.set_value("Employee", emp, "department", dn)
    ins_name = frappe.db.get_value("Instructor", {"instructor_name": person})
    if not ins_name: continue
    try:
        doc = frappe.get_doc("Instructor", ins_name)
        doc.department = dn
        doc.set("instructor_log", [])
        for ay, term, prog, course, grp in sorted(logs.get(person, []), key=lambda x: (x[0], x[2], x[3])):
            doc.append("instructor_log", {"academic_year": ay, "academic_term": term, "department": dn,
                                          "program": prog, "course": course, "student_group": grp})
        doc.flags.ignore_permissions = True; doc.save(); frappe.db.commit()
    except Exception as e:
        frappe.db.rollback(); errors.append(f"Instructor {person}: {repr(e)[:200]}")

print("\n== VERIFY ==")
print("  instructors with department:", frappe.db.count("Instructor", {"department": ["is", "set"]}), "/",
      frappe.db.count("Instructor"))
print("  employees with department:", frappe.db.count("Employee", {"department": ["is", "set"], "company": COMPANY}),
      "/", frappe.db.count("Employee", {"company": COMPANY}))
print("  instructor log rows:", frappe.db.count("Instructor Log"))
print(f"\nERRORS ({len(errors)}):" if errors else "\nNo errors.")
for x in errors: print("  ", x)
frappe.destroy()
