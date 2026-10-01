"""Shared helpers for the ZanaSchools demo pack. Every script: ZS_SITE=<site> required, dry run unless ZS_APPLY=1."""
import os, sys
import frappe

SITE = os.environ.get("ZS_SITE")
APPLY = os.environ.get("ZS_APPLY") == "1"
if not SITE:
    sys.exit("ZS_SITE=<site> is required")

def connect():
    os.chdir("/home/frappe/frappe-bench/sites")
    frappe.init(site=SITE, sites_path="."); frappe.connect(); frappe.set_user("Administrator")
    company = frappe.defaults.get_global_default("company")
    if not company:
        sys.exit(f"{SITE}: no default company - apply the school blueprint first")
    print(f"site {SITE} | company {company} | {'APPLY' if APPLY else 'DRY RUN (nothing written)'}\n")
    return company

errors, created = [], {}
def attempt(label, fn):
    try:
        r = fn()
        if APPLY: frappe.db.commit()
        return r
    except Exception as e:
        frappe.db.rollback(); errors.append(f"{label}: {repr(e)[:240]}"); frappe.local.message_log = []

def ins(d, submit=False):
    meta = frappe.get_meta(d["doctype"])
    doc = frappe.get_doc({k: v for k, v in d.items() if k == "doctype" or meta.has_field(k)})
    doc.flags.ignore_permissions = True; doc.insert()
    if submit: doc.submit()
    created[d["doctype"]] = created.get(d["doctype"], 0) + 1
    return doc

def finish():
    print("\ncreated:", created or "nothing")
    print(f"ERRORS ({len(errors)}):" if errors else "No errors.")
    for x in errors[:30]: print("  ", x)
    frappe.destroy()
