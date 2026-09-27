# zanaverse_onboarding/blueprint_apply.py
#
# Apply a client blueprint (from the zanaverse_blueprints app) to the current site.
# A blueprint is data only: feature switches plus records files (Custom DocPerm,
# Property Setter, CRM Fields Layout, Workspace ...). Blueprints may `extends` a
# parent (normally _base); parents are applied first, children override.
#
# Usage:
#   bench --site <site> execute zanaverse_onboarding.blueprint_apply.apply --kwargs "{'name': 'mtc', 'dry_run': True}"
#   bench --site <site> execute zanaverse_onboarding.blueprint_apply.apply          # uses site_config zanaverse_blueprint

import json
import os

import frappe
import yaml


def _bp_dir(name):
    return frappe.get_app_path("zanaverse_blueprints", "blueprints", name)


def load_blueprint(name):
    path = os.path.join(_bp_dir(name), "blueprint.yaml")
    if not os.path.exists(path):
        frappe.throw(f"Blueprint '{name}' not found at {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _chain(name, seen=()):
    if name in seen:
        frappe.throw(f"Blueprint inheritance cycle: {list(seen) + [name]}")
    bp = load_blueprint(name)
    parent = bp.get("extends")
    return (_chain(parent, seen + (name,)) if parent else []) + [(name, bp)]


def _import_records(bp_name, entry, installed, dry_run, report):
    rel = entry["file"]
    missing = set(entry.get("requires_apps") or []) - installed
    if missing:
        report.append(f"skip    {bp_name}/{rel}  (needs {sorted(missing)})")
        return
    path = os.path.join(_bp_dir(bp_name), rel)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for d in data if isinstance(data, list) else [data]:
        action = "update" if frappe.db.exists(d["doctype"], d["name"]) else "create"
        report.append(f"{action:7} {d['doctype']}: {d['name']}  ({bp_name}/{rel})")
    if not dry_run:
        from frappe.core.doctype.data_import.data_import import import_doc
        import_doc(path)


def _setup_company(company, dry_run, report):
    if not company:
        return
    if frappe.db.get_single_value("System Settings", "setup_complete"):
        report.append("skip    company setup (site already set up)")
        return
    report.append(f"setup   company {company['name']} ({company['country']}, {company['currency']}, FY {company['fy_start']}..{company['fy_end']})")
    if dry_run:
        return
    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
    first = company["first_user"]
    frappe.flags.mute_emails = True
    try:
        setup_complete({
            "language": company.get("language", "English"),
            "country": company["country"], "timezone": company["timezone"], "currency": company["currency"],
            "full_name": first["full_name"], "email": first["email"], "password": frappe.generate_hash(length=20),
            "company_name": company["name"], "company_abbr": company["abbr"],
            "chart_of_accounts": company.get("chart_of_accounts", "Standard"),
            "fy_start_date": company["fy_start"], "fy_end_date": company["fy_end"], "setup_demo": 0,
        })
    finally:
        frappe.flags.mute_emails = False


def _role_profiles(profiles, dry_run, report):
    for prof in profiles or []:
        exclude = set(prof.get("exclude_roles") or []) | {"Administrator", "Guest", "All"}
        roles = sorted(frappe.get_all("Role", filters={"desk_access": 1, "disabled": 0}, pluck="name"))
        roles = [r for r in roles if r not in exclude]
        report.append(f"profile {prof['name']}: {len(roles)} roles (excluding {sorted(exclude - {'Administrator', 'Guest', 'All'})})")
        if dry_run:
            continue
        doc = frappe.get_doc("Role Profile", prof["name"]) if frappe.db.exists("Role Profile", prof["name"]) else frappe.new_doc("Role Profile")
        doc.role_profile = prof["name"]
        doc.set("roles", [{"role": r} for r in roles])
        doc.save(ignore_permissions=True)


def add_user(email, first_name, last_name="", role_profile=None, roles=None):
    """Provision a person (people never live in blueprints). No welcome email is sent."""
    frappe.flags.mute_emails = True
    try:
        user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.new_doc("User")
        user.update({"email": email, "first_name": first_name, "last_name": last_name, "user_type": "System User", "send_welcome_email": 0})
        if role_profile:
            user.role_profile_name = role_profile
        user.save(ignore_permissions=True)
        if roles:
            user.add_roles(*roles)
        frappe.db.commit()
        print(f"user {email}: profile={role_profile} roles={len(frappe.get_roles(email))}")
    finally:
        frappe.flags.mute_emails = False


def apply(name=None, dry_run=False):
    name = name or frappe.conf.get("zanaverse_blueprint")
    if not name:
        frappe.throw("No blueprint given and none set in site_config (zanaverse_blueprint)")
    installed = set(frappe.get_installed_apps())
    has_settings = bool(frappe.db.exists("DocType", "Zanaverse Settings"))
    report, features = [f"blueprint {name} ({'DRY RUN' if dry_run else 'APPLY'}) on {frappe.local.site}"], {}

    chain = _chain(name)
    company = next((bp.get("company") for _, bp in reversed(chain) if bp.get("company")), None)
    _setup_company(company, dry_run, report)

    profiles = []
    for bp_name, bp in chain:
        features.update(bp.get("features") or {})
        profiles.extend(bp.get("role_profiles") or [])
        for entry in bp.get("records") or []:
            _import_records(bp_name, entry, installed, dry_run, report)
    _role_profiles(profiles, dry_run, report)

    for key, val in features.items():
        report.append(f"feature {key} = {int(bool(val))}")
        if not dry_run and has_settings:
            frappe.db.set_single_value("Zanaverse Settings", key, 1 if val else 0)

    if not dry_run:
        if has_settings:
            frappe.db.set_single_value("Zanaverse Settings", "blueprint", name)
        frappe.db.commit()
        frappe.clear_cache()
    print("\n".join(report))
