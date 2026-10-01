"""
ZanaSchools demo - Phase 5: fees and finance.
Fee categories, income/bank accounts, fee structures (per year group x student category),
fee records for every term of 2025-26 and Term 1 of 2026-27, and payments with realistic
family payment behaviour (prompt / part-payers / late / arrears).

Dry run by default: it runs ONE full probe (structure -> fee -> payment) inside a
transaction and rolls it back, so the whole accounting chain is tested with nothing kept.
ZS_APPLY=1 to write. Safe to re-run.
"""
import os, random, datetime as dt
from collections import defaultdict
import frappe
from frappe.utils import getdate, flt

SITE = "zanaschools-demo.zanaverse.com"
SITES = "/home/frappe/frappe-bench/sites"
APPLY = os.environ.get("ZS_APPLY") == "1"
COMPANY = "Zana International School"
AY_PREV, AY_CUR = "2025-2026", "2026-2027"
TERMS = {
    AY_PREV: [("Term 1", dt.date(2025, 9, 1)), ("Term 2", dt.date(2026, 1, 12)), ("Term 3", dt.date(2026, 5, 4))],
    AY_CUR: [("Term 1", dt.date(2026, 9, 7))],
}
# per-term fees in USD (current year; last year was 5% lower)
TUITION = {"primary": 2500, "ks3": 3000, "igcse": 3500, "alevel": 4000}
DEV_LEVY, ICT_FEE, LAB_FEE, EXAM_FEE, BOARDING, TRANSPORT = 150, 100, 120, 300, 2800, 450
DISCOUNT = {"Scholarship": (0.50, "50% scholarship"), "Staff Child": (0.75, "staff child, 75% discount")}
FEE_CATEGORIES = {"Tuition": "Termly tuition", "Development Levy": "Campus development levy",
                  "ICT & Technology": "Devices, software and connectivity", "Lab Fee": "Science laboratory consumables",
                  "Examination Fee": "External examination board entries", "Boarding": "Boarding and meals",
                  "Transport": "School bus service"}
INCOME_ACCOUNT_NAME = "Tuition & Fees Income"
BANK_ACCOUNT_NAME = "Zenith Bank USD"

errors, created = [], defaultdict(int)
def attempt(label, fn):
    try:
        r = fn()
        if APPLY: frappe.db.commit()
        return r
    except Exception as e:
        frappe.db.rollback(); errors.append(f"{label}: {repr(e)[:260]}"); frappe.local.message_log = []
_meta = {}
def has(dtp, f):
    if dtp not in _meta: _meta[dtp] = frappe.get_meta(dtp)
    return _meta[dtp].has_field(f)
def ins(d, submit=False):
    doc = frappe.get_doc({k: v for k, v in d.items() if k == "doctype" or has(d["doctype"], k)})
    doc.flags.ignore_permissions = True; doc.insert()
    if submit: doc.submit()
    created[d["doctype"]] += 1; return doc
def ynum(p): return int(p.split()[1])
def stage(p):
    n = ynum(p)
    return "primary" if n <= 6 else "ks3" if n <= 9 else "igcse" if n <= 11 else "alevel"

os.chdir(SITES)
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()
frappe.set_user("Administrator")
TODAY = getdate()
print(f"MODE: {'APPLY' if APPLY else 'DRY RUN (probe + rollback)'} | today {TODAY}\n")

co = frappe.db.get_value("Company", COMPANY, ["default_receivable_account", "cost_center", "default_cash_account",
                                              "abbr"], as_dict=True)
RECV, CC, CASH, ABBR = co.default_receivable_account, co.cost_center, co.default_cash_account, co.abbr
INCOME = f"{INCOME_ACCOUNT_NAME} - {ABBR}"
BANK = f"{BANK_ACCOUNT_NAME} - {ABBR}"
income_parent = (frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1, "account_name": "Direct Income"})
                 or frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1, "root_type": "Income"}))
bank_parent = (frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1, "account_type": "Bank"})
               or frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1, "account_name": "Bank Accounts"}))
modes = {m: bool(frappe.db.exists("Mode of Payment", m)) for m in ("Wire Transfer", "Cash", "Cheque", "Bank Draft")}
print("== CHECKS ==")
print(f"  receivable {RECV} | cost centre {CC} | cash {CASH}")
print(f"  income parent {income_parent} | bank parent {bank_parent}")
print(f"  party type Student: {bool(frappe.db.exists('Party Type', 'Student'))} | modes: {modes}")

# ---------------------------------------------------------------- data
pe_rows = frappe.get_all("Program Enrollment", filters={"docstatus": 1},
                         fields=["name", "student", "student_name", "program", "academic_year",
                                 "student_category", "student_batch_name"], limit_page_length=0)
fam_of = {}
for g in frappe.get_all("Student Guardian", filters={"parenttype": "Student"}, fields=["parent", "guardian"],
                        order_by="idx", limit_page_length=0):
    fam_of.setdefault(g.parent, g.guardian)
def fam_rng(s, salt): return random.Random(f"{salt}-{fam_of.get(s, s)}")
def behaviour(s):
    r = fam_rng(s, "pay").random()
    return "prompt" if r < 0.72 else "partial" if r < 0.87 else "late" if r < 0.96 else "arrears"
def uses_transport(s, cat): return cat != "Boarding Student" and fam_rng(s, "bus").random() < 0.35

def components(prog, cat, ay):
    f = 0.95 if ay == AY_PREV else 1.0
    tuition = TUITION[stage(prog)] * f
    desc = "Tuition"
    if cat in DISCOUNT:
        tuition *= 1 - DISCOUNT[cat][0]; desc = f"Tuition ({DISCOUNT[cat][1]})"
    c = [("Tuition", round(tuition / 5) * 5, desc), ("Development Levy", DEV_LEVY, "Development Levy"),
         ("ICT & Technology", ICT_FEE, "ICT & Technology")]
    if stage(prog) != "primary": c.append(("Lab Fee", LAB_FEE, "Lab Fee"))
    if ynum(prog) in (11, 13): c.append(("Examination Fee", EXAM_FEE, "Examination Fee"))
    if cat == "Boarding Student": c.append(("Boarding", BOARDING, "Boarding"))
    return c

jobs = []   # (pe_row, ay, term, term_start)
for r in pe_rows:
    for term, ts in TERMS.get(r.academic_year, []):
        jobs.append((r, r.academic_year, term, ts))

def pay_plan(s, ay, term_idx, due, total):
    """list of (date, amount) payments for one fee record"""
    b, rr = behaviour(s), random.Random(f"p-{s}-{ay}-{term_idx}")
    if ay == AY_PREV:
        if b == "prompt": return [(due - dt.timedelta(days=rr.randint(0, 14)), total)]
        if b == "partial":
            half = round(total * 0.5, 2)
            return [(due - dt.timedelta(days=rr.randint(0, 7)), half), (due + dt.timedelta(days=rr.randint(20, 40)), total - half)]
        if b == "late": return [(due + dt.timedelta(days=rr.randint(20, 45)), total)]
        return [] if term_idx == 2 else [(due + dt.timedelta(days=rr.randint(30, 60)), total)]  # arrears: Term 3 unpaid
    if b == "prompt": return [(min(TODAY, due - dt.timedelta(days=rr.randint(0, 14))), total)]
    if b == "partial": return [(due + dt.timedelta(days=rr.randint(0, 5)), round(total * rr.uniform(0.5, 0.7), 2))]
    return []   # late payers and arrears families: unpaid, now overdue

plan_total = sum(sum(a for _, a, _ in components(r.program, r.student_category, ay)) for r, ay, _, _ in jobs)
print(f"\n== PLAN ==\n  fee records {len(jobs)} ({sum(1 for j in jobs if j[1] == AY_PREV)} for 2025-26, "
      f"{sum(1 for j in jobs if j[1] == AY_CUR)} for this term)")
print(f"  billed before transport ~${plan_total:,.0f}")
beh = defaultdict(int)
for r in pe_rows:
    if r.academic_year == AY_CUR: beh[behaviour(r.student)] += 1
print("  payment behaviour (students this term):", dict(beh))

# ---------------------------------------------------------------- building blocks
CAT_ITEM = {}
def ensure_items():
    ig = "Fee Component" if frappe.db.exists("Item Group", "Fee Component") else "All Item Groups"
    for c, d in FEE_CATEGORIES.items():
        item = frappe.db.get_value("Fee Category", c, "item")
        if not item or not frappe.db.exists("Item", item):
            if not frappe.db.exists("Item", c):
                ins({"doctype": "Item", "item_code": c, "item_name": c, "item_group": ig, "is_stock_item": 0, "is_sales_item": 1, "stock_uom": "Nos", "description": d})
            frappe.db.set_value("Fee Category", c, "item", c)
            item = c
        CAT_ITEM[c] = item

def setup_masters():
    for c, d in FEE_CATEGORIES.items():
        if not frappe.db.exists("Fee Category", c):
            ins({"doctype": "Fee Category", "category_name": c, "description": d})
    ensure_items()
    if not frappe.db.exists("Account", INCOME):
        ins({"doctype": "Account", "account_name": INCOME_ACCOUNT_NAME, "parent_account": income_parent,
             "company": COMPANY, "account_type": "Income Account", "account_currency": "USD"})
    if not frappe.db.exists("Account", BANK):
        ins({"doctype": "Account", "account_name": BANK_ACCOUNT_NAME, "parent_account": bank_parent,
             "company": COMPANY, "account_type": "Bank", "account_currency": "USD"})

structures = {}
def structure(prog, cat, ay):
    key = (prog, cat, ay)
    if key in structures: return structures[key]
    name = frappe.db.get_value("Fee Structure", {"program": prog, "student_category": cat, "academic_year": ay,
                                                 "docstatus": 1})
    if not name:
        name = ins({"doctype": "Fee Structure", "program": prog, "academic_year": ay, "student_category": cat,
                    "company": COMPANY, "receivable_account": RECV, "income_account": INCOME, "cost_center": CC,
                    "components": [{"fees_category": c, "item": CAT_ITEM.get(c), "amount": a, "description": d}
                                   for c, a, d in components(prog, cat, ay)]}, submit=True).name
    structures[key] = name
    return name

def make_fee(r, ay, term, ts):
    comps = components(r.program, r.student_category, ay)
    if uses_transport(r.student, r.student_category): comps.append(("Transport", TRANSPORT, "Transport"))
    return ins({"doctype": "Fees", "student": r.student, "student_name": r.student_name, "program_enrollment": r.name,
                "program": r.program, "academic_year": ay, "academic_term": f"{ay} ({term})",
                "fee_structure": structure(r.program, r.student_category, ay), "company": COMPANY,
                "posting_date": ts - dt.timedelta(days=21), "due_date": ts, "currency": "USD",
                "receivable_account": RECV, "income_account": INCOME, "cost_center": CC,
                "student_category": r.student_category, "student_batch": r.student_batch_name,
                "components": [{"fees_category": c, "item": CAT_ITEM.get(c), "amount": a, "description": d} for c, a, d in comps]},
               submit=True)

def make_payment(fee, amount, date, seed):
    rr = random.Random(seed)
    mode = rr.choices(["Wire Transfer", "Cheque", "Cash"], [70, 20, 10])[0]
    amt = flt(amount, 2)
    pe = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Receive", "company": COMPANY, "posting_date": date, "party_type": "Student", "party": fee.student, "party_name": fee.student_name, "paid_from": fee.receivable_account, "paid_from_account_currency": "USD", "paid_to": CASH if mode == "Cash" else BANK, "paid_to_account_currency": "USD", "paid_amount": amt, "received_amount": amt, "source_exchange_rate": 1, "target_exchange_rate": 1, "reference_no": f"ZIS-{rr.randint(100000, 999999)}", "reference_date": date, "mode_of_payment": mode if modes.get(mode) else None, "references": [{"reference_doctype": "Fees", "reference_name": fee.name, "due_date": fee.due_date, "total_amount": flt(fee.grand_total), "outstanding_amount": flt(fee.outstanding_amount), "allocated_amount": amt, "exchange_rate": 1}]})
    pe.flags.ignore_permissions = True
    pe.insert(); pe.submit()
    created["Payment Entry"] += 1
    return pe

# ---------------------------------------------------------------- dry run: probe and roll back
if not APPLY:
    print("\n== PROBE (rolled back) ==")
    try:
        setup_masters()
        r, ay, term, ts = next(j for j in jobs if j[1] == AY_CUR)
        fee = make_fee(r, ay, term, ts)
        print(f"  fee OK: {fee.name} {r.student_name} total {fee.grand_total} outstanding {fee.outstanding_amount}")
        pe = make_payment(fee, fee.grand_total / 2, ts, "probe")
        print(f"  payment OK: {pe.name} {pe.paid_amount} -> outstanding now "
              f"{frappe.db.get_value('Fees', fee.name, 'outstanding_amount')}")
        gl = frappe.db.count("GL Entry", {"voucher_no": ["in", [fee.name, pe.name]], "is_cancelled": 0})
        print(f"  GL entries posted: {gl}")
        print("  PROBE PASSED")
    except Exception as e:
        print("  PROBE FAILED:", repr(e)[:500])
    frappe.db.rollback()
    frappe.destroy(); print("\nDry run complete (nothing kept)."); raise SystemExit

# ---------------------------------------------------------------- apply
print("\n== 1. Fee categories & accounts ==")
attempt("masters", setup_masters)
print("== 2. Fee records + payments (several minutes) ==")
existing_fee = {(f.student, f.academic_term): f.name for f in frappe.get_all(
    "Fees", filters={"docstatus": 1}, fields=["name", "student", "academic_term"], limit_page_length=0)}
for i, (r, ay, term, ts) in enumerate(jobs):
    if i and i % 100 == 0:
        print(f"   {i}/{len(jobs)}"); frappe.db.commit()
    term_idx = [t for t, _ in TERMS[ay]].index(term)
    fname = existing_fee.get((r.student, f"{ay} ({term})"))
    if not fname:
        fee = attempt(f"Fees {r.student} {ay} {term}", lambda: make_fee(r, ay, term, ts))
        if not fee: continue
        fname = fee.name
    fee = frappe.get_doc("Fees", fname)
    if flt(fee.outstanding_amount) < flt(fee.grand_total): continue      # payments already recorded
    for k, (date, amount) in enumerate(pay_plan(r.student, ay, term_idx, ts, flt(fee.grand_total))):
        if date > TODAY: continue
        date = max(date, fee.posting_date)
        attempt(f"Payment {fname} #{k}", lambda: make_payment(frappe.get_doc("Fees", fname), amount, date,
                                                              f"{fname}-{k}"))

# ---------------------------------------------------------------- verify
print("\n== VERIFY ==")
for d in ["Fee Category", "Fee Structure", "Fees", "Payment Entry"]:
    print(f"  {d}: {frappe.db.count(d, {'docstatus': 1} if d in ('Fee Structure', 'Fees', 'Payment Entry') else None)}")
for ay in (AY_PREV, AY_CUR):
    t = frappe.db.sql("""select count(*) n, sum(grand_total) billed, sum(outstanding_amount) outstanding,
        sum(outstanding_amount = 0) paid, sum(outstanding_amount > 0 and outstanding_amount < grand_total) part,
        sum(outstanding_amount = grand_total) unpaid from `tabFees` where docstatus = 1 and academic_year = %s""",
                      ay, as_dict=True)[0]
    if t.n:
        print(f"  {ay}: {t.n} records | billed ${flt(t.billed):,.0f} | outstanding ${flt(t.outstanding):,.0f} "
              f"| paid {t.paid}, part-paid {t.part}, unpaid {t.unpaid}")
print(f"  overdue now: {frappe.db.count('Fees', {'docstatus': 1, 'outstanding_amount': ['>', 0], 'due_date': ['<', TODAY]})}")
print("  created this run:", dict(created))
print(f"\nERRORS ({len(errors)}):" if errors else "\nNo errors.")
for x in errors[:30]: print("  ", x)
if len(errors) > 30: print(f"   ... and {len(errors) - 30} more")
frappe.destroy()
