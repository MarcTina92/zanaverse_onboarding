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


def apply(name=None, dry_run=False):
    name = name or frappe.conf.get("zanaverse_blueprint")
    if not name:
        frappe.throw("No blueprint given and none set in site_config (zanaverse_blueprint)")
    installed = set(frappe.get_installed_apps())
    has_settings = bool(frappe.db.exists("DocType", "Zanaverse Settings"))
    report, features = [f"blueprint {name} ({'DRY RUN' if dry_run else 'APPLY'}) on {frappe.local.site}"], {}

    for bp_name, bp in _chain(name):
        features.update(bp.get("features") or {})
        for entry in bp.get("records") or []:
            _import_records(bp_name, entry, installed, dry_run, report)

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
    return report
