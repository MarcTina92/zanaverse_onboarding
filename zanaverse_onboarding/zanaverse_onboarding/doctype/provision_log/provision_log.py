from frappe.model.document import Document
import frappe, uuid, json

class ProvisionLog(Document):
    pass

def make_log(site, blueprint, dry_run, summary, plan, status, commit_sha=None):
    doc = frappe.get_doc({
        "doctype": "Provision Log",
        "log_id": str(uuid.uuid4())[:8],
        "site": site,
        "blueprint": blueprint,
        "dry_run": 1 if dry_run else 0,
        "summary": summary,
        "plan": json.dumps(plan, indent=2),
        "status": status,
        "commit_sha": commit_sha
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name
