"""
ZanaSchools v16 staging - Phase 5b: bill through Fee Schedule -> Sales Invoice (per student).
1. setup: item income defaults, USD selling price list
2. retire legacy Fees + their payments (cancel with ledger reversal, delete)
3. Fee Schedule per (year group, student category, term) + one Sales Invoice per student
4. payments against invoices, same family behaviour as Phase 5
Dry run = full probe (one schedule -> invoice -> payment -> portal API) then ROLLBACK.
ZS_APPLY=1 to write. Safe to re-run.
"""
import os, random, datetime as dt
from collections import defaultdict
import frappe
from frappe.utils import getdate, flt

SITE = "zanaschools-staging.zanaverse.com"
SITES = "/home/frappe/frappe-bench/sites"
APPLY = os.environ.get("ZS_APPLY") == "1"
COMPANY = "Zana International School"
AY_PREV, AY_CUR = "2025-2026", "2026-2027"
TERMS = {AY_PREV: [("Term 1", dt.date(2025, 9, 1)), ("Term 2", dt.date(2026, 1, 12)), ("Term 3", dt.date(2026, 5, 4))],
         AY_CUR: [("Term 1", dt.date(2026, 9, 7))]}
PRICE_LIST = "ZIS School Fees (USD)"
TRANSPORT = 450

errors, created = [], defaultdict(int)
def attempt(label, fn):
    try:
        r = fn()
        if APPLY: frappe.db.commit()
        return r
    except Exception as e:
        frappe.db.rollback(); errors.append(f"{label}: {repr(e)[:260]}"); frappe.local.message_log = []

os.chdir(SITES)
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()
frappe.set_user("Administrator")
from education.education.doctype.fee_schedule.fee_schedule import get_fees_mapped_doc, get_customer_from_student, get_students
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
TODAY = getdate()
print(f"MODE: {'APPLY' if APPLY else 'DRY RUN (probe + rollback)'} | today {TODAY}\n")

abbr = frappe.db.get_value("Company", COMPANY, "abbr")
INCOME, BANK = f"Tuition & Fees Income - {abbr}", f"Zenith Bank USD - {abbr}"
CASH = frappe.db.get_value("Company", COMPANY, "default_cash_account")
CC = frappe.db.get_value("Company", COMPANY, "cost_center")
override = (frappe.get_hooks("override_whitelisted_methods") or {}).get("education.education.api.get_student_invoices")
print("== CHECKS ==")
print(f"  income {INCOME}: {bool(frappe.db.exists('Account', INCOME))} | bank {BANK}: {bool(frappe.db.exists('Account', BANK))} | cash {CASH} | cc {CC}")
print(f"  legacy Fees: {frappe.db.count('Fees', {'docstatus': 1})} | legacy payments: {frappe.db.count('Payment Entry', {'docstatus': 1})}")
print(f"  fee structures: {frappe.db.count('Fee Structure', {'docstatus': 1})} | Sales Invoice has 'student' field: {frappe.get_meta('Sales Invoice').has_field('student')}")
print(f"  portal fees override hook: {override or 'none (standard Education code)'}")

# ---------------------------------------------------------------- family behaviour (identical to Phase 5)
fam_of = {}
for g in frappe.get_all("Student Guardian", filters={"parenttype": "Student"}, fields=["parent", "guardian"],
                        order_by="idx", limit_page_length=0):
    fam_of.setdefault(g.parent, g.guardian)
def fam_rng(s, salt): return random.Random(f"{salt}-{fam_of.get(s, s)}")
def behaviour(s):
    r = fam_rng(s, "pay").random()
    return "prompt" if r < 0.72 else "partial" if r < 0.87 else "late" if r < 0.96 else "arrears"
def uses_transport(s, cat): return cat != "Boarding Student" and fam_rng(s, "bus").random() < 0.35
def pay_plan(s, ay, t_idx, due, total):
    b, rr = behaviour(s), random.Random(f"p-{s}-{ay}-{t_idx}")
    if ay == AY_PREV:
        if b == "prompt": return [(due - dt.timedelta(days=rr.randint(0, 14)), total)]
        if b == "partial":
            half = round(total * 0.5, 2)
            return [(due - dt.timedelta(days=rr.randint(0, 7)), half), (due + dt.timedelta(days=rr.randint(20, 40)), total - half)]
        if b == "late": return [(due + dt.timedelta(days=rr.randint(20, 45)), total)]
        return [] if t_idx == 2 else [(due + dt.timedelta(days=rr.randint(30, 60)), total)]
    if b == "prompt": return [(min(TODAY, due - dt.timedelta(days=rr.randint(0, 14))), total)]
    if b == "partial": return [(due + dt.timedelta(days=rr.randint(0, 5)), round(total * rr.uniform(0.5, 0.7), 2))]
    return []

# ---------------------------------------------------------------- building blocks
WH = frappe.db.get_value("Warehouse", {"company": COMPANY, "warehouse_name": "Stores"}) or frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0})
def setup():
    frappe.db.set_single_value("Stock Settings", "default_warehouse", WH)
    if not frappe.db.exists("Price List", PRICE_LIST):
        frappe.get_doc({"doctype": "Price List", "price_list_name": PRICE_LIST, "currency": "USD",
                        "selling": 1, "enabled": 1}).insert(ignore_permissions=True)
    for item in frappe.get_all("Fee Category", pluck="item"):
        if not item: continue
        doc = frappe.get_doc("Item", item)
        if True:
            doc.set("item_defaults", [{"company": COMPANY, "income_account": INCOME, "selling_cost_center": CC, "default_warehouse": WH}])
            doc.flags.ignore_permissions = True; doc.save()

def wait_queue(limit=150):
    import time
    from frappe.utils.background_jobs import get_queue
    while sum(get_queue(q).count for q in ("default", "short", "long")) > limit:
        time.sleep(5)

def retire_legacy():
    frappe.db.set_single_value("Accounts Settings", "delete_linked_ledger_entries", 1)
    for dt_name in ("Payment Entry", "Fees"):
        names = frappe.get_all(dt_name, filters={"docstatus": ["<", 2]} if dt_name == "Fees" else
                               {"docstatus": ["<", 2], "party_type": "Student"}, pluck="name", limit_page_length=0)
        print(f"   retiring {len(names)} {dt_name}")
        for i, n in enumerate(names):
            def go(n=n):
                wait_queue(); d = frappe.get_doc(dt_name, n)
                if d.docstatus == 1:
                    d.flags.ignore_links = True; d.flags.ignore_permissions = True; d.cancel()
                frappe.delete_doc(dt_name, n, force=1, ignore_permissions=True, delete_permanently=True)
            attempt(f"retire {dt_name} {n}", go)
            if i and i % 200 == 0: print(f"     {i}/{len(names)}")

def schedule_for(prog, cat, ay, term, ts, groups):
    fs = frappe.db.get_value("Fee Structure", {"program": prog, "student_category": cat, "academic_year": ay, "docstatus": 1})
    if not fs: return None
    existing = frappe.db.get_value("Fee Schedule", {"fee_structure": fs, "academic_term": f"{ay} ({term})",
                                                    "docstatus": 1})
    if existing: return existing
    comps = frappe.get_all("Fee Component", filters={"parent": fs}, fields=["fees_category", "item", "description", "amount"],
                           order_by="idx")
    doc = frappe.get_doc({
        "doctype": "Fee Schedule", "fee_structure": fs, "program": prog, "student_category": cat,
        "academic_year": ay, "academic_term": f"{ay} ({term})", "company": COMPANY, "currency": "USD",
        "posting_date": ts - dt.timedelta(days=21), "due_date": ts, "cost_center": CC,
        "receivable_account": frappe.db.get_value("Company", COMPANY, "default_receivable_account"),
        "student_groups": [{"student_group": g} for g in groups],
        "components": [{"fees_category": c.fees_category, "item": c.item, "description": c.description,
                        "amount": c.amount, "total": c.amount} for c in comps]})
    doc.flags.ignore_permissions = True
    doc.insert()
    # student list filtering by term would drop Term 2/3 (enrolments carry Term 1); schedule stays year-scoped for selection
    doc.submit()
    created["Fee Schedule"] += 1
    return doc.name

def invoice_for(fsched, student, cat):
    existing = frappe.db.get_value("Sales Invoice", {"fee_schedule": fsched, "student": student, "docstatus": 1})
    if existing: return frappe.get_doc("Sales Invoice", existing)
    si = get_fees_mapped_doc(fee_schedule=fsched, doctype="Sales Invoice", student_id=student,
                             customer=get_customer_from_student(student))
    si.company = COMPANY; si.currency = "USD"; si.conversion_rate = 1
    si.selling_price_list = PRICE_LIST; si.price_list_currency = "USD"; si.plc_conversion_rate = 1
    si.set_posting_time = 1; si.ignore_pricing_rule = 1
    for it in si.items:
        it.qty = 1; it.rate = it.price_list_rate; it.income_account = INCOME; it.cost_center = CC
    if uses_transport(student, cat):
        si.append("items", {"item_code": frappe.db.get_value("Fee Category", "Transport", "item") or "Transport",
                            "qty": 1, "price_list_rate": TRANSPORT, "rate": TRANSPORT,
                            "income_account": INCOME, "cost_center": CC})
    si.flags.ignore_permissions = True
    si.insert(); si.submit()
    created["Sales Invoice"] += 1
    return si

def pay(si, amount, date, seed):
    rr = random.Random(seed)
    mode = rr.choices(["Wire Transfer", "Cheque", "Cash"], [70, 20, 10])[0]
    pe = get_payment_entry("Sales Invoice", si.name)
    amt = flt(amount, 2)
    pe.posting_date = date
    pe.paid_to = CASH if mode == "Cash" else BANK
    pe.paid_amount = pe.received_amount = amt
    pe.references[0].allocated_amount = amt
    pe.reference_no = f"ZIS-{rr.randint(100000, 999999)}"; pe.reference_date = date
    if frappe.db.exists("Mode of Payment", mode): pe.mode_of_payment = mode
    pe.flags.ignore_permissions = True
    pe.insert(); pe.submit()
    created["Payment Entry"] += 1

# ---------------------------------------------------------------- plan
units = []   # (ay, term idx, term, ts, program, category, [groups])
for ay in (AY_PREV, AY_CUR):
    groups_by_prog = defaultdict(list)
    for g in frappe.get_all("Student Group", filters={"academic_year": ay, "group_based_on": "Batch"}, fields=["name", "program"]):
        groups_by_prog[g.program].append(g.name)
    cats_by_prog = defaultdict(set)
    for r in frappe.get_all("Program Enrollment", filters={"academic_year": ay, "docstatus": 1},
                            fields=["program", "student_category"], limit_page_length=0):
        cats_by_prog[r.program].add(r.student_category)
    for t_idx, (term, ts) in enumerate(TERMS[ay]):
        for prog, groups in sorted(groups_by_prog.items()):
            for cat in sorted(cats_by_prog[prog]):
                units.append((ay, t_idx, term, ts, prog, cat, groups))
print(f"\n== PLAN ==\n  fee schedules: {len(units)}")

def run_unit(u, limit=None):
    ay, t_idx, term, ts, prog, cat, groups = u
    fsched = schedule_for(prog, cat, ay, term, ts, groups)
    if not fsched: raise Exception(f"no fee structure for {prog}/{cat}/{ay}")
    done = 0
    for g in groups:
        for st in get_students(g, ay, None, cat):
            si = invoice_for(fsched, st.student, cat)
            if flt(si.outstanding_amount) >= flt(si.grand_total):   # no payments recorded yet
                for k, (date, amount) in enumerate(pay_plan(st.student, ay, t_idx, ts, flt(si.grand_total))):
                    if date > TODAY: continue
                    pay(frappe.get_doc("Sales Invoice", si.name), amount, max(date, getdate(si.posting_date)), f"{si.name}-{k}")
            done += 1
            if limit and done >= limit: return si
    return None

# ---------------------------------------------------------------- dry run probe
if not APPLY:
    print("\n== PROBE (rolled back) ==")
    try:
        setup()
        u = next(x for x in units if x[0] == AY_CUR)
        si = run_unit(u, limit=1)
        si = frappe.get_doc("Sales Invoice", si.name)
        print(f"  invoice OK: {si.name} {si.customer_name} | items {[(i.item_code, i.amount) for i in si.items]} "
              f"| total {si.grand_total} | outstanding {si.outstanding_amount} | status {si.status} | debit_to {si.debit_to}")
        print(f"  GL entries: {frappe.db.count('GL Entry', {'voucher_no': si.name, 'is_cancelled': 0})}")
        from education.education import api
        student_user = frappe.db.get_value("Student", si.student, "user")
        print(f"  standard portal API sees it: {any(r['invoice'] == si.name for r in api.get_student_invoices(si.student)['invoices'])}")
        print("  PROBE PASSED")
    except Exception as e:
        import traceback; traceback.print_exc(); print("  PROBE FAILED:", repr(e)[:400])
    frappe.db.rollback(); frappe.destroy(); print("\nDry run complete (nothing kept)."); raise SystemExit

# ---------------------------------------------------------------- apply
print("\n== 1. setup =="); attempt("setup", setup)
print("== 2. retire legacy Fees =="); retire_legacy()
print("== 3. schedules, invoices, payments (15-25 min) ==")
for i, u in enumerate(units):
    wait_queue(); attempt(f"unit {u[4]}/{u[5]}/{u[0]} {u[2]}", lambda u=u: run_unit(u))
    if i % 10 == 0: print(f"   {i}/{len(units)} schedules | invoices {created['Sales Invoice']} | payments {created['Payment Entry']}")

print("\n== VERIFY ==")
print(f"  legacy Fees left: {frappe.db.count('Fees')}")
for ay in (AY_PREV, AY_CUR):
    t = frappe.db.sql("""select count(*) n, sum(si.grand_total) billed, sum(si.outstanding_amount) outstanding,
        sum(si.status='Paid') paid, sum(si.status='Partly Paid') part, sum(si.status in ('Unpaid','Overdue')) unpaid,
        sum(si.status='Overdue') overdue
        from `tabSales Invoice` si join `tabFee Schedule` fs on fs.name = si.fee_schedule
        where si.docstatus=1 and fs.academic_year=%s""", ay, as_dict=True)[0]
    print(f"  {ay}: {t.n} invoices | billed ${flt(t.billed):,.0f} | outstanding ${flt(t.outstanding):,.0f} "
          f"| paid {t.paid}, part {t.part}, unpaid {t.unpaid} (overdue {t.overdue})")
print("  created:", dict(created))
print(f"\nERRORS ({len(errors)}):" if errors else "\nNo errors.")
for x in errors[:25]: print("  ", x)
frappe.destroy()
