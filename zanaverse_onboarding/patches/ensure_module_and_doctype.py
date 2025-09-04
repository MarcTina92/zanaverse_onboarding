import frappe

MODULE_NAME = "Zanaverse Onboarding"
APP_NAME = "zanaverse_onboarding"

def _ensure_module_def():
    # Create Module Def if it doesn't exist (works across Frappe versions)
    if not frappe.db.exists("Module Def", MODULE_NAME):
        doc = frappe.get_doc({
            "doctype": "Module Def",
            "module_name": MODULE_NAME,
            "app_name": APP_NAME
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

def execute():
    _ensure_module_def()
    # Reload our DocType so controller path resolves to our app
    try:
        frappe.reload_doc(APP_NAME, "doctype", "provision_log")
    except Exception:
        # Don't break migrations if reload isn't strictly necessary yet
        frappe.db.rollback()
