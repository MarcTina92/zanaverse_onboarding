"""Demo pack 01: academic calendar. Years 2025-26 (history), 2026-27 (current), 2027-28 (admissions);
terms; fiscal year 2025-26 for last year's billing; holiday calendar as company default; current year/term."""
import datetime as dt
import frappe
from _common import connect, attempt, ins, finish, APPLY

YEARS = {
    "2025-2026": ("2025-09-01", "2026-08-31", [("Term 1", "2025-09-01", "2025-12-05"), ("Term 2", "2026-01-12", "2026-04-10"), ("Term 3", "2026-05-04", "2026-07-24")]),
    "2026-2027": ("2026-09-01", "2027-08-31", [("Term 1", "2026-09-07", "2026-12-11"), ("Term 2", "2027-01-11", "2027-04-01"), ("Term 3", "2027-04-26", "2027-07-16")]),
    "2027-2028": ("2027-09-01", "2028-08-31", [("Term 1", "2027-09-06", "2027-12-10")]),
}
FISCAL = [("2025-2026", "2025-04-01", "2026-03-31"), ("2026-2027", "2026-04-01", "2027-03-31")]
HOLIDAY_LIST = "School Calendar 2025-2027"
HOLIDAYS = {
    "2025-10-01": "Independence Day", "2025-12-25": "Christmas Day", "2025-12-26": "Boxing Day",
    "2026-01-01": "New Year's Day", "2026-03-20": "Eid al-Fitr", "2026-04-03": "Good Friday",
    "2026-04-06": "Easter Monday", "2026-05-01": "Workers' Day", "2026-06-12": "Democracy Day",
    "2026-10-01": "Independence Day", "2026-12-25": "Christmas Day", "2026-12-28": "Boxing Day (observed)",
    "2027-01-01": "New Year's Day", "2027-03-10": "Eid al-Fitr", "2027-03-26": "Good Friday",
    "2027-03-29": "Easter Monday", "2027-05-17": "Eid al-Adha",
}
for s, e in [("2025-10-27", "2025-10-31"), ("2026-02-16", "2026-02-20"), ("2026-05-25", "2026-05-29"),
             ("2026-10-26", "2026-10-30"), ("2027-02-15", "2027-02-19"), ("2027-05-31", "2027-06-04")]:
    d = dt.date.fromisoformat(s)
    while d <= dt.date.fromisoformat(e):
        HOLIDAYS.setdefault(str(d), "Half Term"); d += dt.timedelta(days=1)

company = connect()

print("== fiscal years ==")
for name, s, e in FISCAL:
    have = frappe.db.get_value("Fiscal Year", {"year_start_date": s}) or frappe.db.exists("Fiscal Year", name)
    print(f"  {name}: {'exists' if have else 'create'}")
    if not have and APPLY:
        attempt(f"FY {name}", lambda name=name, s=s, e=e: ins({"doctype": "Fiscal Year", "year": name, "year_start_date": s, "year_end_date": e}))

print("== academic years & terms ==")
for ay, (s, e, terms) in YEARS.items():
    have = frappe.db.exists("Academic Year", ay)
    print(f"  {ay}: {'exists' if have else 'create'}")
    if not have and APPLY:
        attempt(f"AY {ay}", lambda ay=ay, s=s, e=e: ins({"doctype": "Academic Year", "academic_year_name": ay, "year_start_date": s, "year_end_date": e}))
    for tn, ts, te in terms:
        full = f"{ay} ({tn})"
        have = frappe.db.exists("Academic Term", full)
        print(f"    {full}: {'exists' if have else 'create'}")
        if not have and APPLY:
            attempt(f"term {full}", lambda ay=ay, tn=tn, ts=ts, te=te: ins({"doctype": "Academic Term", "academic_year": ay, "term_name": tn, "term_start_date": ts, "term_end_date": te}))

print("== holiday calendar ==")
have = frappe.db.exists("Holiday List", HOLIDAY_LIST)
print(f"  {HOLIDAY_LIST}: {'exists' if have else 'create'} ({len(HOLIDAYS)} holidays + weekends)")
if not have and APPLY:
    def mk():
        rows, d = [], dt.date(2025, 9, 1)
        while d <= dt.date(2027, 8, 31):
            if str(d) in HOLIDAYS: rows.append({"holiday_date": d, "description": HOLIDAYS[str(d)], "weekly_off": 0})
            elif d.weekday() >= 5: rows.append({"holiday_date": d, "description": d.strftime("%A"), "weekly_off": 1})
            d += dt.timedelta(days=1)
        ins({"doctype": "Holiday List", "holiday_list_name": HOLIDAY_LIST, "from_date": "2025-09-01", "to_date": "2027-08-31", "holidays": rows})
    attempt("holiday list", mk)
if APPLY:
    frappe.db.set_value("Company", company, "default_holiday_list", HOLIDAY_LIST)
    frappe.db.set_single_value("Education Settings", "current_academic_year", "2026-2027")
    frappe.db.set_single_value("Education Settings", "current_academic_term", "2026-2027 (Term 1)")
    frappe.db.commit()
print("  company default holiday list + current year/term (2026-2027, Term 1):", "set" if APPLY else "would set")
finish()
