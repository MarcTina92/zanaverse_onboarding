# zanaverse_onboarding/blueprint_extras.py
#
# Optional blueprint sections, added for industry/tenant blueprints (first used by `school`).
# All are opt-in: blueprints that do not use them behave exactly as before.
#
#   vars:         free-form values for this tenant (merged parent -> child)
#   site_config:  keys written to the site's site_config.json         e.g. {host_name: "https://{{ site }}"}
#   assets:       files copied from the blueprint folder to /files/   e.g. [assets/crest.svg]
#   settings:     field values on Single DocTypes ("Website Settings") or named docs ("Role:Student")
#
# Strings in site_config / settings, and the whole text of record files, are rendered with Jinja
# using: site, company (the blueprint's company block), vars, abbr (company abbr shortcut).

import json
import os
import tempfile

import frappe

CONTEXT = {}


def _merge(a, b):
    out = dict(a or {})
    for k, v in (b or {}).items():
        out[k] = _merge(out.get(k), v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _render(value):
    if isinstance(value, str) and "{{" in value:
        return frappe.render_template(value, CONTEXT)
    if isinstance(value, dict):
        return {k: _render(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v) for v in value]
    return value


def build_context(chain, company):
    vars_ = {}
    for _, bp in chain:
        vars_ = _merge(vars_, bp.get("vars"))
    company = company or {}
    CONTEXT.clear()
    CONTEXT.update({"site": frappe.local.site, "company": company, "abbr": company.get("abbr", ""), "vars": vars_})
    return CONTEXT


def render_record_file(bp_dir, rel):
    """Return a path to the record file, rendered through Jinja if it contains template tags."""
    path = os.path.join(bp_dir, rel)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "{{" not in text and "{%" not in text:
        return path
    rendered = frappe.render_template(text, CONTEXT)
    json.loads(rendered)  # fail early with a clear error if the template broke the JSON
    fd, tmp = tempfile.mkstemp(prefix="zv-bp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(rendered)
    return tmp


def apply_site_config(chain, dry_run, report):
    conf = {}
    for _, bp in chain:
        conf.update(bp.get("site_config") or {})
    if not conf:
        return
    from frappe.installer import update_site_config
    for key, val in _render(conf).items():
        report.append(f"config  {key} = {val!r}")
        if not dry_run:
            update_site_config(key, val)
            frappe.conf[key] = val


def apply_assets(chain, bp_dir_fn, dry_run, report):
    """Copy files to the site's public /files/<name>. Settings/records reference that URL directly.
    No File records are created: Frappe renames a file it finds already on disk, which made re-applies
    leave duplicate records with hashed names."""
    for bp_name, bp in chain:
        for rel in bp.get("assets") or []:
            src = os.path.join(bp_dir_fn(bp_name), rel)
            name = os.path.basename(rel)
            if not os.path.exists(src):
                report.append(f"MISSING asset {bp_name}/{rel}")
                continue
            dest = frappe.get_site_path("public", "files", name)
            report.append(f"{'update' if os.path.exists(dest) else 'create':7} asset /files/{name}  ({bp_name}/{rel})")
            if dry_run:
                continue
            with open(src, "rb") as f:
                data = f.read()
            with open(dest, "wb") as f:
                f.write(data)


def apply_settings(chain, dry_run, report):
    merged = {}
    for _, bp in chain:
        merged = _merge(merged, bp.get("settings"))
    for target, fields in _render(merged).items():
        doctype, _, name = target.partition(":")
        single = frappe.get_meta(doctype).issingle
        if not single and not frappe.db.exists(doctype, name):
            report.append(f"skip    settings {target} (not found)")
            continue
        for field, val in (fields or {}).items():
            report.append(f"set     {target}.{field} = {val!r}")
            if dry_run:
                continue
            if single:
                frappe.db.set_single_value(doctype, field, val)
            else:
                frappe.db.set_value(doctype, name, field, val)


def only_missing(path, data, bp_name, rel, report):
    """For create_only record files: keep existing records untouched, import only the missing ones."""
    docs = data if isinstance(data, list) else [data]
    missing = []
    for d in docs:
        if frappe.db.exists(d["doctype"], d["name"]):
            report.append(f"keep    {d['doctype']}: {d['name']}  ({bp_name}/{rel}, create_only)")
        else:
            missing.append(d)
    if not missing:
        return path, []
    fd, tmp = tempfile.mkstemp(prefix="zv-bp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(missing, f)
    return tmp, missing
