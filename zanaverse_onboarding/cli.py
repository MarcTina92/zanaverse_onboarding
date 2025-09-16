# apps/zanaverse_onboarding/zanaverse_onboarding/cli.py

from __future__ import annotations

import os
import json
import glob
import pathlib
import click
import frappe

# Optional deps & fallbacks
try:
    from frappe.exceptions import DuplicateEntryError
except Exception:
    class DuplicateEntryError(Exception):
        ...

try:
    import yaml
except Exception:
    yaml = None

# Optional: workspace hardening helper (don’t explode if missing)
try:
    from zanaverse_onboarding.provisioning.restrict_standard_workspaces import (
        restrict_standard_workspaces,
    )
except Exception:
    restrict_standard_workspaces = None


# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------

APP_ROOT = frappe.get_app_path("zanaverse_onboarding")
BP_ROOT = os.path.join(APP_ROOT, "blueprints")


# --------------------------------------------------------------------------------------
# YAML + doc merging helpers
# --------------------------------------------------------------------------------------

def _read_yaml(path: str) -> dict:
    if not yaml or not os.path.exists(path):
        return {"docs": []}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "docs" not in data:
        data["docs"] = []
    return data


def _ensure_name(d: dict) -> dict:
    if d.get("name"):
        return d
    if d.get("title"):
        d["name"] = d["title"]
    if d.get("doctype") == "Sales Taxes and Charges Template" and d.get("title"):
        nm = d["title"]
        if d.get("company"):
            nm = f"{nm} - {d['company']}"
        d["name"] = nm
    return d


def _ensure_required_fields(d: dict) -> dict:
    dt = d.get("doctype")
    if dt == "Brand":
        d.setdefault("brand", d.get("name"))
    if dt == "Company":
        d.setdefault("company_name", d.get("name"))
    if dt == "Sales Taxes and Charges Template":
        d.setdefault("title", d.get("name"))
    if dt == "Role Profile":
        d.setdefault("role_profile", d.get("name"))
    return d


def _resolve_tax_template_name(d: dict) -> str | None:
    if d.get("doctype") != "Sales Taxes and Charges Template":
        return None
    title = d.get("title") or d.get("name")
    if not title:
        return None
    company = d.get("company")

    filters = {"title": title}
    if company:
        filters["company"] = company
    existing = frappe.db.get_value("Sales Taxes and Charges Template", filters, "name")
    if existing:
        return existing

    candidates = [title]
    if company:
        candidates.append(f"{title} - {company}")
        abbr = frappe.db.get_value("Company", company, "abbr")
        if abbr:
            candidates.append(f"{title} - {abbr}")

    for nm in candidates:
        if frappe.db.exists("Sales Taxes and Charges Template", nm):
            return nm
    return None


def _merge_docs(doc_sets: list[dict]) -> list[dict]:
    merged = {}
    for ds in doc_sets:
        for d in ds.get("docs", []):
            d = _ensure_required_fields(_ensure_name(dict(d)))
            doctype, name = d.get("doctype"), d.get("name")
            if not doctype or not name:
                frappe.throw(f"Each doc needs doctype+name (or title): {d}")
            key = (doctype, name)
            base = merged.get(key, {})
            merged[key] = {**base, **d}
    return list(merged.values())


# --------------------------------------------------------------------------------------
# Workspace compare normalizers (idempotent updates)
# --------------------------------------------------------------------------------------

_WS_KEEP = {
    "type", "label", "icon", "description", "hidden",
    "link_type", "link_to", "url", "doc_view", "kanban_board",
    "report_ref_doctype", "is_query_report", "dependencies",
    "only_for", "onboard", "color", "format", "stats_filter", "link_count",
}
_WS_CHILD_TABLES = ("links", "shortcuts", "charts", "number_cards", "quick_lists", "custom_blocks")


def _coerce_bool_int(v):
    if isinstance(v, bool):
        return 1 if v else 0
    return v


def _is_trivial(v):
    return v in (None, "", 0, [], {})


def _clean_row(row: dict) -> dict:
    out = {}
    for k in _WS_KEEP:
        if k in row:
            v = _coerce_bool_int(row.get(k))
            if not _is_trivial(v):
                if isinstance(v, str):
                    v = v.strip()
                    if not v:
                        continue
                out[k] = v
    return out


def _normalize_workspace_rows(rows):
    cleaned = [_clean_row(r or {}) for r in (rows or [])]
    cleaned = [r for r in cleaned if r]
    cleaned.sort(key=lambda x: (
        x.get("type", ""), x.get("label", ""),
        x.get("link_type", ""), x.get("link_to", ""),
        x.get("doc_view", ""), x.get("url", "")
    ))
    return cleaned


def _normalize_for_compare(d):
    d = dict(d)
    d.pop("content", None)
    if d.get("doctype") == "Workspace":
        d.pop("sequence_id", None)
        d.pop("onboarding_list", None)  
        for t in _WS_CHILD_TABLES:
            if t in d:
                d[t] = _normalize_workspace_rows(d.get(t))
    return d


# --------------------------------------------------------------------------------------
# Collect blueprint files
# --------------------------------------------------------------------------------------

def _collect_blueprint(client_slug: str) -> tuple[list[dict], str]:
    client_dir = os.path.join(BP_ROOT, client_slug)
    client_files = sorted(glob.glob(os.path.join(client_dir, "*.yaml")))
    doc_sets = [_read_yaml(p) for p in client_files]
    docs = _merge_docs(doc_sets)
    assets_dir = os.path.join(client_dir, "assets")
    return docs, assets_dir


# --------------------------------------------------------------------------------------
# Module helpers (ensure Module Def exists)
# --------------------------------------------------------------------------------------

def _ensure_module_def(module: str, app_default: str = "zanaverse_onboarding"):
    if frappe.db.exists("Module Def", {"module_name": module}):
        return
    fields = {df.fieldname for df in frappe.get_meta("Module Def").fields}
    payload = {"doctype": "Module Def", "module_name": module}
    if "app_name" in fields:
        payload["app_name"] = app_default
    elif "app" in fields:
        payload["app"] = app_default
    frappe.get_doc(payload).insert(ignore_permissions=True)


def _ensure_modules_for_docs(docs, app_default: str = "zanaverse_onboarding"):
    modules = sorted({
        d.get("module") for d in docs
        if d.get("doctype") == "Workspace" and d.get("module")
    })
    for m in modules:
        _ensure_module_def(m, app_default)

def _coerce_workspace_json_in_payload(payload: dict) -> None:
    """Mutate payload in-place so Workspace JSON fields are strings."""
    if (payload or {}).get("doctype") == "Workspace":
        for k in ("content", "onboarding_list"):
            if k in payload:
                payload[k] = _jsonify_array(payload[k])


# --------------------------------------------------------------------------------------
# Plan changes & apply
# --------------------------------------------------------------------------------------

def _plan_changes(docs):
    plan = {"create": [], "update": [], "noop": []}
    for d in docs:
        d = dict(d)
        doctype, name = d["doctype"], d["name"]

        if doctype == "Sales Taxes and Charges Template":
            resolved = _resolve_tax_template_name(d)
            if resolved:
                name = resolved
                d["name"] = resolved

        exists = frappe.db.exists(doctype, name)
        if not exists:
            plan["create"].append(d)
        else:
            current = frappe.get_doc(doctype, name).as_dict()
            cur_n = _normalize_for_compare(current)
            new_n = _normalize_for_compare(d)
            delta = {k: v for k, v in new_n.items()
                     if k not in ("doctype", "name") and cur_n.get(k) != v}
            if delta:
                plan["update"].append({"doctype": doctype, "name": name, **delta})
            else:
                plan["noop"].append({"doctype": doctype, "name": name})
    return plan


def _apply_plan(plan):
    applied = {"created": [], "updated": []}

    for d in plan["create"]:
        payload = dict(d)
        if payload["doctype"] == "Sales Taxes and Charges Template":
            payload.pop("name", None)
        _coerce_workspace_json_in_payload(payload)
        try:
            doc = frappe.get_doc(payload)
            doc.insert(ignore_permissions=True)
            applied["created"].append((payload["doctype"], doc.name))
        except DuplicateEntryError:
            if payload["doctype"] == "Sales Taxes and Charges Template":
                existing = _resolve_tax_template_name(d)
                if existing:
                    doc = frappe.get_doc(payload["doctype"], existing)
                    for k, v in d.items():
                        if k in ("doctype", "name"):
                            continue
                        doc.set(k, v)
                    doc.save(ignore_permissions=True)
                    applied["updated"].append((payload["doctype"], existing))
                else:
                    raise
            else:
                raise

    for d in plan["update"]:
        doc = frappe.get_doc(d["doctype"], d["name"])
        for k, v in d.items():
            if k in ("doctype", "name"):
                continue
            if k in ("content", "onboarding_list") and d["doctype"] == "Workspace":
                v = _jsonify_array(v)
            doc.set(k, v)
        doc.save(ignore_permissions=True)
        applied["updated"].append((d["doctype"], d["name"]))

    frappe.db.commit()
    return applied


# --------------------------------------------------------------------------------------
# Baselines & logging
# --------------------------------------------------------------------------------------

def _ensure_baselines():
    if frappe.db.exists("DocType", "Warehouse Type"):
        needed = ["Transit", "Finished Goods", "Work In Progress", "Stores"]
        for wt in needed:
            if not frappe.db.exists("Warehouse Type", wt):
                try:
                    frappe.get_doc({"doctype": "Warehouse Type", "name": wt}).insert(ignore_permissions=True)
                except Exception:
                    try:
                        frappe.get_doc({"doctype": "Warehouse Type", "warehouse_type_name": wt}).insert(ignore_permissions=True)
                    except Exception:
                        frappe.log_error(frappe.get_traceback(), f"Seed Warehouse Type failed: {wt}")
        frappe.db.commit()


def _safe_log(*a, **kw):
    try:
        from .doctype.provision_log.provision_log import make_log
        return make_log(*a, **kw)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ProvisionLog write failed")
        return None


# --------------------------------------------------------------------------------------
# Simple YAML loaders (companies/brands/roles/users)
# --------------------------------------------------------------------------------------

def _load_simple_yaml(bp, filename):
    path = os.path.join(BP_ROOT, bp, filename)
    if not yaml or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ensure_custom_field(doctype, fieldname, label, fieldtype, options=None, insert_after=None, in_list_view=0):
    cf_name = f"{doctype}-{fieldname}"
    if frappe.db.exists("Custom Field", cf_name):
        return cf_name
    meta = frappe.get_meta(doctype)
    if insert_after and not meta.has_field(insert_after):
        insert_after = None
    doc = frappe.new_doc("Custom Field")
    doc.dt = doctype
    doc.fieldname = fieldname
    doc.label = label
    doc.fieldtype = fieldtype
    doc.options = options or ""
    if insert_after:
        doc.insert_after = insert_after
    doc.in_list_view = in_list_view
    doc.name = cf_name
    doc.save(ignore_permissions=True)
    frappe.clear_cache(doctype=doctype)
    return cf_name


_BRAND_TARGETS = [
    "Lead", "Opportunity", "Customer", "Quotation", "Sales Order",
    "Project", "Task", "Employee", "Job Applicant", "Job Opening",
]


def _apply_brand_custom_fields_if_needed():
    from zanaverse_onboarding import permissions as perm
    pol = perm._load_policy()
    needs_brand = any((cfg.get("brand_field") or "").strip()
                      for cfg in (pol.get("pqc_doctypes") or {}).values())
    if not needs_brand:
        return
    for dt in _BRAND_TARGETS:
        _ensure_custom_field(dt, "brand", "Brand", "Link", options="Brand", insert_after="company")


def _apply_companies_from_yaml(bp):
    data = _load_simple_yaml(bp, "companies.yaml")
    for c in (data.get("companies") or []):
        name = c.get("company_name")
        if not name:
            continue
        if frappe.db.exists("Company", name):
            doc = frappe.get_doc("Company", name)
            if c.get("abbr"):
                doc.abbr = c["abbr"]
            if c.get("default_currency"):
                doc.default_currency = c["default_currency"]
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "Company",
                "company_name": name,
                "abbr": c.get("abbr"),
                "default_currency": c.get("default_currency"),
            }).insert(ignore_permissions=True)


def _apply_brands_from_yaml(bp):
    data = _load_simple_yaml(bp, "brands.yaml")
    for b in (data.get("brands") or []):
        name = b.get("brand")
        if not name:
            continue
        if frappe.db.exists("Brand", name):
            continue
        frappe.get_doc({"doctype": "Brand", "brand": name, "name": name}).insert(ignore_permissions=True)


# ---- module profiles (from module_profiles.yaml) ----------------------------

def _apply_module_profiles_from_yaml(bp: str):
    """
    Reads blueprints/<bp>/module_profiles.yaml with schema:

    module_profiles:
      - name: "ESS"
        description: "..."
        modules: ["HR", "Payroll", ...]
        workspaces: ["HR", "Payroll", ...]   # note: stored only for union/hardening, not in DocType
      - name: "ESS+Sales"
        extends: "ESS"
        modules: [...]
        workspaces: [...]
      ...

    Behavior:
      - Resolves 'extends' chains by UNION for both modules & workspaces.
      - Upserts DocType "Module Profile":
          module_profile_name = <name>
          modules child table  = [{"module": "<Module Name>"}...]
      - 'workspaces' are merged and kept in memory for later use if you want,
        but the Module Profile record only stores modules.
    """
    path = os.path.join(BP_ROOT, bp, "module_profiles.yaml")
    if not yaml or not os.path.exists(path):
        return

    data = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
    items = data.get("module_profiles") or []
    if not items:
        return

    # index by name
    by_name = {row.get("name"): row for row in items if row.get("name")}
    resolved: dict[str, dict] = {}

    def _merge_one(name: str, stack: list[str] | None = None) -> dict:
        if name in resolved:
            return resolved[name]
        if name not in by_name:
            raise Exception(f"module_profile '{name}' not found in YAML")
        stack = stack or []
        if name in stack:
            raise Exception(f"extends cycle detected: {' -> '.join(stack + [name])}")

        cur = dict(by_name[name] or {})
        base = cur.get("extends")
        if base:
            parent = _merge_one(base, stack + [name])
            modules = sorted(set((parent.get("modules") or []) + (cur.get("modules") or [])))
            workspaces = sorted(set((parent.get("workspaces") or []) + (cur.get("workspaces") or [])))
            merged = {
                "name": name,
                "description": cur.get("description") or parent.get("description") or "",
                "modules": modules,
                "workspaces": workspaces,
            }
        else:
            merged = {
                "name": name,
                "description": cur.get("description") or "",
                "modules": sorted(set(cur.get("modules") or [])),
                "workspaces": sorted(set(cur.get("workspaces") or [])),
            }
        resolved[name] = merged
        return merged

    # resolve everything
    for n in by_name:
        _merge_one(n)

    # upsert Module Profiles
    for name, prof in resolved.items():
        rows = [{"module": m} for m in (prof.get("modules") or [])]

        if frappe.db.exists("Module Profile", name):
            doc = frappe.get_doc("Module Profile", name)
            # overwrite description & module rows atomically
            doc.description = prof.get("description") or ""
            doc.set("modules", rows)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "Module Profile",
                "module_profile_name": name,
                "description": prof.get("description") or "",
                "modules": rows,
            }).insert(ignore_permissions=True)

    frappe.db.commit()

# ---- roles cloning (optional union-only helper) ------------------------------

from typing import Dict, Any, Tuple, List
#from frappe.permissions import add_permission

def _ensure_role_doc(role_name: str, desk_access: bool | None, dry_run: bool) -> tuple[bool, bool]:
    created = updated = False
    exists = frappe.db.exists("Role", role_name)
    if not exists:
        if dry_run:
            return True, False
        doc = frappe.get_doc({"doctype": "Role", "role_name": role_name})
        if desk_access is not None:
            doc.desk_access = int(bool(desk_access))
        doc.insert(ignore_permissions=True)
        created = True
    else:
        if desk_access is not None:
            current = int(frappe.db.get_value("Role", role_name, "desk_access") or 0)
            new_val = int(bool(desk_access))
            if current != new_val:
                if not dry_run:
                    frappe.db.set_value("Role", role_name, "desk_access", new_val)
                updated = True
    return created, updated


def _custom_docperm_columns() -> set[str]:
    meta = frappe.get_meta("Custom DocPerm", cached=True)
    base = {"parent", "parenttype", "parentfield", "role", "permlevel"}
    return base | {df.fieldname for df in meta.fields}


def _perm_key(row: Dict[str, Any]) -> Tuple[str, int]:
    return (row.get("parent"), int(row.get("permlevel") or 0))


def _fetch_base_perms(base_role: str) -> List[Dict[str, Any]]:
    stock = frappe.get_all("DocPerm", filters={"role": base_role}, fields=["*"]) or []
    custom = frappe.get_all("Custom DocPerm", filters={"role": base_role}, fields=["*"]) or []
    rows: List[Dict[str, Any]] = []
    for r in stock + custom:
        r = dict(r)
        r["parenttype"] = "DocType"
        r["parentfield"] = "permissions"
        rows.append(r)
    return rows


def _merge_bool_flags(dst: Dict[str, Any], src: Dict[str, Any], allowed: set[str]) -> bool:
    changed = False
    for k in allowed:
        if k in {"name", "parent", "parenttype", "parentfield", "role", "permlevel"}:
            continue
        vs = src.get(k)
        if isinstance(vs, (int, bool)):
            vd = int(dst.get(k) or 0)
            vn = 1 if (int(bool(vs)) or vd) else 0
            if vn != vd:
                dst[k] = vn
                changed = True
    return changed


def clone_roles_from_yaml(blueprint: str = "mtc", dry_run: int = 1) -> dict:
    dry_run = int(dry_run or 0)
    cfg = _load_simple_yaml(blueprint, "roles.yaml") or {}
    roles_cfg = cfg.get("roles") or []
    union_only = bool((cfg.get("options") or {}).get("union_only", True))

    if not roles_cfg:
        return {"ok": False, "message": "roles.yaml missing or empty", "blueprint": blueprint}

    allowed = _custom_docperm_columns()
    summary = {
        "created_roles": [],
        "updated_roles": [],
        "created_perms": 0,
        "updated_perms": 0,
        "union_only": union_only,
        "dry_run": bool(dry_run),
    }

    for row in roles_cfg:
        target = row.get("name") or row.get("role")
        bases = row.get("clone_from") or []
        if isinstance(bases, str):
            bases = [bases]
        desk_access = row.get("desk_access", None)

        if not target or not bases:
            frappe.throw(f"Invalid roles.yaml row (need name & clone_from): {row}")

        created, updated = _ensure_role_doc(target, desk_access, dry_run=bool(dry_run))
        if created:
            summary["created_roles"].append(target)
        if updated:
            summary["updated_roles"].append(target)

        existing: dict[tuple[str, int], dict] = {}
        rows = frappe.get_all("Custom DocPerm", filters={"role": target}, fields=["*"]) or []
        for r in rows:
            existing[_perm_key(r)] = dict(r)

        src_rows: list[dict] = []
        for base in bases:
            if frappe.db.exists("Role", base):
                src_rows.extend(_fetch_base_perms(base))

        for src in src_rows:
            parent, plevel = _perm_key(src)
            if not parent:
                continue

            payload = {k: src.get(k) for k in allowed if k in src}
            payload.update({
                "parent": parent,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": target,
                "permlevel": int(src.get("permlevel") or 0),
            })

            if (parent, plevel) in existing:
                dst = existing[(parent, plevel)]
                if _merge_bool_flags(dst, payload, allowed):
                    summary["updated_perms"] += 1
                    if not dry_run:
                        for k, v in dst.items():
                            if k in {"name", "parent", "parenttype", "parentfield", "role", "permlevel"}:
                                continue
                            if k in allowed and isinstance(v, (int, bool)):
                                frappe.db.set_value("Custom DocPerm", dst["name"], k, int(bool(v)))
                continue

            summary["created_perms"] += 1
            if not dry_run:
                doc = frappe.get_doc({"doctype": "Custom DocPerm", **payload})
                doc.insert(ignore_permissions=True)

    if not dry_run:
        frappe.db.commit()

    return {"ok": True, "blueprint": blueprint, **summary}


# ---- roles from roles.yaml (simple) -----------------------------------------

def _apply_roles_from_yaml(bp):
    data = _load_simple_yaml(bp, "roles.yaml")
    for r in (data.get("roles") or []):
        name = r.get("role")
        if not name:
            continue
        vals = {"role_name": name, "desk_access": int(r.get("desk_access", 1))}
        if frappe.db.exists("Role", name):
            doc = frappe.get_doc("Role", name)
            for k, v in vals.items():
                setattr(doc, k, v)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({"doctype": "Role", "name": name, **vals}).insert(ignore_permissions=True)


# ---- role profiles & users --------------------------------------------------

def _apply_role_profiles_from_yaml(bp, union_only=True):
    data = _load_simple_yaml(bp, "role_profiles.yaml")
    profiles = data.get("role_profiles") or []
    created = updated = 0

    old_flag = getattr(frappe.flags, "in_migrate", False)
    frappe.flags.in_migrate = True
    try:
        for rp in profiles:
            name = rp.get("name")
            roles = list(dict.fromkeys(rp.get("roles") or []))
            if not name:
                continue

            if frappe.db.exists("Role Profile", name):
                doc = frappe.get_doc("Role Profile", name)
                is_new = False
            else:
                doc = frappe.new_doc("Role Profile")
                doc.role_profile = name
                is_new = True

            have = {r.role for r in (doc.roles or [])}
            add = [r for r in roles if r not in have]
            for r in add:
                doc.append("roles", {"role": r})

            if not union_only:
                keep = set(roles)
                doc.roles = [row for row in doc.roles if row.role in keep]

            doc.save(ignore_permissions=True)
            if is_new:
                created += 1
            elif add or (not union_only and have - set(roles)):
                updated += 1
    finally:
        frappe.flags.in_migrate = old_flag

    frappe.db.commit()
    print(f"Applied Role Profiles: created={created}, updated={updated}, total={len(profiles)}")
    return {"ok": True, "created": created, "updated": updated, "total": len(profiles)}


def _ensure_user_doc(u, defaults):
    email = u["email"]
    user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.new_doc("User")

    user.email = email
    user.first_name = u.get("full_name") or email.split("@")[0]
    user.language = u.get("language") or defaults.get("language")
    user.time_zone = u.get("time_zone") or defaults.get("time_zone")
    user.enabled = 1
    user.send_welcome_email = 0
    user.user_type = "System User" if bool(u.get("is_desk_user", True)) else "Website User"
    mp = (u.get("module_profile") or "").strip()
    if mp and frappe.db.exists("Module Profile", mp):
        pass  # module_profile removed (using roles + default_workspace)
    user.save(ignore_permissions=True)

    profiles = []
    if u.get("role_profile"):
        profiles.append(u["role_profile"])
    if u.get("role_profiles"):
        profiles.extend(u["role_profiles"] if isinstance(u["role_profiles"], list) else [u["role_profiles"]])

    profile_roles = set()
    for rp_name in profiles:
        if not rp_name or not frappe.db.exists("Role Profile", rp_name):
            if rp_name and not frappe.db.exists("Role Profile", rp_name):
                frappe.log_error(f"Role Profile not found: {rp_name}", "provision users")
            continue
        rp = frappe.get_doc("Role Profile", rp_name)
        for rr in rp.roles or []:
            if rr.role:
                profile_roles.add(rr.role)

    extra_roles = set(u.get("roles") or [])
    target_roles = profile_roles | extra_roles

    have = {r.role for r in user.roles}
    added = False
    for rname in sorted(target_roles):
        if rname and rname not in have:
            user.append("roles", {"role": rname})
            added = True
    if added:
        user.save(ignore_permissions=True)

    return user


def _ensure_user_permission(user, allow, for_value):
    if not (allow and for_value):
        return
    if not frappe.db.exists(allow, for_value):
        return
    if not frappe.db.exists("User Permission", {"user": user.name, "allow": allow, "for_value": for_value}):
        up = frappe.new_doc("User Permission")
        up.user = user.name
        up.allow = allow
        up.for_value = for_value
        up.insert(ignore_permissions=True)


def _apply_users_from_yaml(bp):
    cfg = _load_simple_yaml(bp, "users.yaml")
    defaults = cfg.get("defaults", {})
    for u in (cfg.get("users") or []):
        user = _ensure_user_doc(u, defaults)
        comp = u.get("company")
        if comp:
            _ensure_user_permission(user, "Company", comp)
        scope = u.get("brand_scope")
        if scope and scope != "All":
            for b in (scope if isinstance(scope, list) else [scope]):
                _ensure_user_permission(user, "Brand", b)


# --------------------------------------------------------------------------------------
# JSON safety helpers for Workspace.content / onboarding_list
# --------------------------------------------------------------------------------------

def _jsonify_array(value) -> str:
    """Return a JSON string representing an array (never None)."""
    if isinstance(value, str):
        v = value.strip()
        if v.startswith("[") and v.endswith("]"):
            return v
        if not v:
            return "[]"
        return frappe.as_json([v])
    if isinstance(value, list):
        return frappe.as_json(value)
    if value in (None, {}, ()):
        return "[]"
    return frappe.as_json([value])


def _ensure_workspace_json_columns(name: str, content=None, onboarding_list=None):
    """Force JSON columns to valid JSON strings."""
    if content is not None:
        frappe.db.set_value("Workspace", name, "content", _jsonify_array(content))
    else:
        cur = frappe.db.get_value("Workspace", name, "content")
        frappe.db.set_value("Workspace", name, "content", _jsonify_array(cur))

    if onboarding_list is not None:
        frappe.db.set_value("Workspace", name, "onboarding_list", _jsonify_array(onboarding_list))
    else:
        cur = frappe.db.get_value("Workspace", name, "onboarding_list")
        frappe.db.set_value("Workspace", name, "onboarding_list", _jsonify_array(cur))


def _normalize_all_workspaces_json():
    # belt-and-suspenders: make sure no workspace has NULL/blank JSON columns
    frappe.db.sql("update `tabWorkspace` set onboarding_list='[]' where onboarding_list is null or onboarding_list=''")
    frappe.db.sql("update `tabWorkspace` set content='[]'          where content is null or content=''")
    frappe.db.commit()


# --------------------------------------------------------------------------------------
# Workspace YAML application (idempotent)
# --------------------------------------------------------------------------------------

def _set_children(doc, fieldname, items):
    if items is None:
        return
    doc.set(fieldname, [])
    for row in items:
        r = dict(row)
        r.pop("doctype", None)
        doc.append(fieldname, r)


# add params
def _apply_workspace_yaml(path: pathlib.Path, include_names: tuple[str, ...] | None = None,
                          include_modules: tuple[str, ...] | None = None):
    if yaml is None:
        frappe.throw("PyYAML is required to apply workspace blueprints.")
    data = yaml.safe_load(path.read_text()) or {}
    docs = data.get("docs", [])
    applied = []

    for d in docs:
        if d.get("doctype") != "Workspace":
            continue

        name = d.get("name") or d.get("title") or d.get("label")
        if not name:
            continue

        # NEW: skip if not included
        if include_names and name not in include_names:
            continue
        if include_modules and (d.get("module") or "") not in include_modules:
            continue

        desired_content = d.get("content", "[]")
        desired_onboarding = d.get("onboarding_list", [])

        if frappe.db.exists("Workspace", name):
            doc = frappe.get_doc("Workspace", name)
            child_keys = {"links","shortcuts","charts","number_cards","quick_lists","custom_blocks","roles"}
            json_keys = {"content","onboarding_list"}
            for k, v in d.items():
                if k in child_keys or k in json_keys or k in {"doctype"}:
                    continue
                doc.set(k, v)
            # replace child tables
            _set_children(doc, "roles", d.get("roles"))
            _set_children(doc, "links", d.get("links"))
            _set_children(doc, "shortcuts", d.get("shortcuts"))
            _set_children(doc, "charts", d.get("charts"))
            _set_children(doc, "number_cards", d.get("number_cards"))
            _set_children(doc, "quick_lists", d.get("quick_lists"))
            _set_children(doc, "custom_blocks", d.get("custom_blocks"))

            doc.flags.ignore_permissions = True
            doc.save()
            _ensure_workspace_json_columns(doc.name, desired_content, desired_onboarding)
            applied.append(("updated", doc.name))
        else:
            newd = dict(d)
            newd.pop("name", None)
            newd["content"] = _jsonify_array(desired_content)
            newd["onboarding_list"] = _jsonify_array(desired_onboarding)
            doc = frappe.get_doc(newd)
            doc.flags.ignore_permissions = True
            doc.insert()
            _ensure_workspace_json_columns(doc.name, desired_content, desired_onboarding)
            applied.append(("created", doc.name))

    _normalize_all_workspaces_json()
    print("Applied:", applied)


def apply_blueprint(files=None, include_names: tuple[str, ...] | None = None,
                    include_modules: tuple[str, ...] | None = None):
    if not files:
        default = frappe.get_app_path(
            "zanaverse_onboarding", "blueprints", "workspaces.yaml"
        )
        files = [default]
    for f in files:
        _apply_workspace_yaml(pathlib.Path(f), include_names=include_names, include_modules=include_modules)

# --------------------------------------------------------------------------------------
# Letterheads: copy repo assets -> site /files + upsert Letter Head docs
# --------------------------------------------------------------------------------------

def _ensure_public_file(local_path: str, public_url: str):
    """Copy an image from repo into /public/files/... and register a public File doc."""
    assert public_url.startswith("/files/")
    target_rel = public_url[len("/files/"):].lstrip("/")
    target_abs = frappe.utils.get_site_path("public", "files", target_rel)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    with open(local_path, "rb") as src, open(target_abs, "wb") as dst:
        dst.write(src.read())

    if not frappe.db.exists("File", {"file_url": public_url, "is_private": 0}):
        frappe.get_doc({
            "doctype": "File",
            "file_url": public_url,
            "is_private": 0
        }).insert(ignore_permissions=True)

def _upsert_letterhead(row: dict):
    """Create/update Letter Head pointing to image URL."""
    name = row["name"]
    if frappe.db.exists("Letter Head", name):
        doc = frappe.get_doc("Letter Head", name)
    else:
        doc = frappe.new_doc("Letter Head")
        doc.letter_head_name = name

    doc.source = row.get("source", "Image")
    doc.content = row.get("content", "") or ""
    if row.get("image"):
        doc.image = row["image"]
    # leave is_default as-is unless you want to force it
    doc.save(ignore_permissions=True)

def _load_letterheads_yaml(bp: str) -> dict:
    """Lightweight loader for blueprints/<bp>/letterheads.yaml."""
    path = os.path.join(BP_ROOT, bp, "letterheads.yaml")
    if not yaml or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def apply_letterheads(bp: str, dry_run: bool = False):
    conf = _load_letterheads_yaml(bp)
    if not conf:
        return

    asset_dir = os.path.join(BP_ROOT, bp, "assets", "letterheads")
    rows = conf.get("letterheads") or []

    # 1) stage file ops + upserts
    for row in rows:
        public_url = row.get("image")
        source_path = row.get("source_path")
        if public_url and source_path:
            local_path = os.path.join(asset_dir, source_path)
            if not os.path.exists(local_path):
                frappe.throw(f"Missing letterhead asset: {local_path}")
            if not dry_run:
                _ensure_public_file(local_path, public_url)
        if not dry_run:
            _upsert_letterhead(row)

    # 2) cache names once
    all_names = frappe.get_all("Letter Head", pluck="name")
    all_names_set = set(all_names)

    preferred = (conf.get("preferred_default") or "").strip()
    keep = set(conf.get("keep_enabled") or [])
    if preferred:
        keep.add(preferred)

    # Validate lists using cached sets
    if preferred and preferred not in all_names_set:
        frappe.throw(f"preferred_default not found: {preferred}")
    missing = [nm for nm in keep if nm not in all_names_set]
    if missing:
        frappe.throw(f"keep_enabled letterheads not found: {missing}")

    # 3) bulk flips
    if not dry_run:
        # clear current default
        frappe.db.sql("update `tabLetter Head` set is_default = 0 where is_default = 1")

        # set preferred default (and ensure it's enabled)
        if preferred:
            frappe.db.set_value("Letter Head", preferred, "is_default", 1)
            frappe.db.set_value("Letter Head", preferred, "disabled", 0)

        # If a preferred exists but keep is empty, lock it down to just preferred
        if not keep and preferred:
            frappe.db.sql(
                "update `tabLetter Head` set is_default = 0, disabled = 1 where name != %s",
                preferred,
            )
            # paranoia: guarantee preferred stays enabled
            frappe.db.set_value("Letter Head", preferred, "disabled", 0)

        # If keep is provided, enable those and disable the rest
        if keep:
            keep_tuple = tuple(keep)
            marks = ", ".join(["%s"] * len(keep_tuple))
            # enable keep
            frappe.db.sql(
                f"update `tabLetter Head` set disabled = 0 where name in ({marks})",
                keep_tuple,
            )
            # disable not-keep
            frappe.db.sql(
                f"update `tabLetter Head` set is_default = 0, disabled = 1 where name not in ({marks})",
                keep_tuple,
            )

        # Fallback: if no preferred default was specified, pick a sane enabled one
        if not preferred:
            cur_default = frappe.db.get_value(
                "Letter Head", {"is_default": 1, "disabled": 0}, "name"
            )
            if not cur_default:
                candidate = (next((nm for nm in keep if nm in all_names_set), None)
                             if keep else None)
                if not candidate:
                    enabled = frappe.get_all(
                        "Letter Head", filters={"disabled": 0}, pluck="name"
                    )
                    candidate = enabled[0] if enabled else None
                if candidate:
                    frappe.db.set_value("Letter Head", candidate, "is_default", 1)

        # 4) per-company defaults — cache companies first
        companies = set(frappe.get_all("Company", pluck="name"))
        for company, lh in (conf.get("company_defaults") or {}).items():
            if company in companies and lh in all_names_set:
                frappe.db.set_value("Company", company, "default_letter_head", lh)

        frappe.db.commit()


# --------------------------------------------------------------------------------------
# Provision entrypoint (for full blueprint runs)
# --------------------------------------------------------------------------------------

@frappe.whitelist()
def provision(
    blueprint: str,
    dry_run: int = 0,
    commit_sha: str | None = None,
    # default OFF
    harden_workspaces: int = 0,
):
    site = frappe.local.site
    dry_run = int(dry_run or 0)

    # Read an optional site flag; falls back to the function arg (default 0/off)
    try:
        from frappe.utils import cint
        conf = (getattr(frappe.local, "conf", None) or {})
        harden = cint(conf.get("zanaverse_harden_workspaces", harden_workspaces))
    except Exception:
        harden = int(harden_workspaces or 0)

    docs, assets_dir = _collect_blueprint(blueprint)
    # Role Profiles handled by a separate helper below
    docs = [d for d in docs if (d.get("doctype") or "") != "Role Profile"]

    plan = _plan_changes(docs)
    summary_text = f"Create: {len(plan['create'])}, Update: {len(plan['update'])}, Noop: {len(plan['noop'])}"

    ws_summary = {}
    applied = {"created": [], "updated": []}

    # DRY RUN
    if dry_run:
        try:
            if harden and restrict_standard_workspaces:
                ws_summary = restrict_standard_workspaces(
                    dry_run=True,
                    include_modules=None,
                    exclude_names=("Zanaverse Home",),
                    force=False,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Workspace hardening (dry-run) failed")

        _safe_log(site, blueprint, True, summary_text, plan, "DRY-RUN", commit_sha)
        payload = {"summary": summary_text, "plan": plan, "workspace_hardening": ws_summary}
        print(json.dumps(payload, indent=2))
        return payload

    # APPLY
    _ensure_baselines()
    _ensure_modules_for_docs(docs, app_default="zanaverse_onboarding")
    applied = _apply_plan(plan)

    _apply_companies_from_yaml(blueprint)
    _apply_brands_from_yaml(blueprint)
    _apply_brand_custom_fields_if_needed()

    # clone_roles_from_yaml(blueprint=blueprint, dry_run=0)  # optional
    _apply_role_profiles_from_yaml(blueprint, union_only=True)
    _apply_module_profiles_from_yaml(blueprint)   
    _apply_users_from_yaml(blueprint)

    # Only harden if explicitly enabled
    try:
        if harden and restrict_standard_workspaces:
            ws_summary = restrict_standard_workspaces(
                dry_run=False,
                include_modules=None,
                exclude_names=("Zanaverse Home",),
                force=False,
            )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Workspace hardening failed")

    # letterheads/assets (if any) — driven by letterheads.yaml
    apply_letterheads(blueprint)

    # single commit at the end of provisioning
    frappe.db.commit()

    # log + return
    _safe_log(site, blueprint, False, summary_text, plan, "SUCCESS", commit_sha)
    payload = {
        "summary": summary_text,
        "applied": applied,
        "workspace_hardening": ws_summary,
    }
    print(json.dumps(payload, indent=2))
    return payload


# --------------------------------------------------------------------------------------
# Doctor command (nice-to-have)
# --------------------------------------------------------------------------------------

@click.command("zv-doctor")
@click.option("--site", "site_name", help="Frappe site to use (bench also accepts --site).")
def doctor(site_name: str | None = None):
    """Sanity-check policy.yaml against DocType metadata and show registered PQCs."""
    import os as _os

    site = getattr(frappe.local, "site", None) or site_name or _os.environ.get("FRAPPE_SITE")
    if not site:
        click.echo("No site context. Run as: bench --site <your-site> zv-doctor")
        return

    did_connect = False
    if getattr(frappe.local, "site", None) != site:
        frappe.init(site=site)
        frappe.connect()
        did_connect = True

    try:
        from zanaverse_onboarding import permissions as perm

        pol = perm._load_policy()
        print("strict_default_deny:", pol.get("strict_default_deny"))
        print("pqc_bypass_roles:", pol.get("pqc_bypass_roles"))

        hook_map = frappe.get_hooks("permission_query_conditions")
        print("\nRegistered PQCs for policy doctypes:")
        problems = []

        for dt, cfg in (pol.get("pqc_doctypes") or {}).items():
            if not (cfg and cfg.get("enabled")):
                continue

            fn = f"zanaverse_onboarding.permissions.pqc_{dt.lower().replace(' ', '_')}"
            hooked = fn in (hook_map.get(dt) or [])
            print(f" - {dt}: {fn}  (hooked: {hooked})")

            cf = (cfg.get("company_field") or "").strip()
            bf = (cfg.get("brand_field") or "").strip()
            meta = frappe.get_meta(dt, cached=True)

            has_c = bool(cf) and meta.has_field(cf)
            has_b = bool(bf) and meta.has_field(bf)

            if (cf and not has_c) or (bf and not has_b):
                problems.append({
                    "doctype": dt,
                    "company_field": cf, "company_exists": has_c,
                    "brand_field": bf,   "brand_exists": has_b,
                })

        if problems:
            print("\n⚠️  Field mismatches found:")
            for p in problems:
                print(" ", p)
        else:
            print("\n✅ Policy fields match DocTypes.")
    finally:
        if did_connect:
            frappe.destroy()


# cli.py

def apply_default_workspaces_after_migrate():
    try:
        _normalize_all_workspaces_json()

        bp = (frappe.local.conf or {}).get("zanaverse_onboarding_blueprint")
        if not bp:
            return

        p = pathlib.Path(frappe.get_app_path("zanaverse_onboarding", "blueprints", bp, "workspaces.yaml"))
        if not p.exists():
            return

        apply_blueprint(
            files=(str(p),),
            include_names=("Home",),  # <- only re-apply “Home”
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "apply_default_workspaces_after_migrate failed")

@frappe.whitelist()
def verify_workspace_visibility_invariants(allowed_private_no_roles=("Wiki",), raise_on_error=False):
    """Verify public/private + roles invariants for Workspace, but skip gracefully
    on stacks that don't have the 'Workspace Role' child doctype."""
    allowed = set(allowed_private_no_roles or ())

    # If Workspace itself is missing, nothing to verify.
    if not frappe.db.table_exists("tabWorkspace"):
        print("No Workspace table on this stack; skipping invariants check.")
        return {"ok": True, "skipped": "no Workspace table"}

    # Some stacks don't have a 'Workspace Role' child doctype/table.
    has_ws_role = frappe.db.table_exists("tabWorkspace Role")

    public = set(frappe.get_all("Workspace", filters={"public": 1}, pluck="name"))

    roles = set()
    if has_ws_role:
        role_rows = frappe.get_all("Workspace Role", fields=["parent"], distinct=True)
        roles = {r["parent"] for r in (role_rows or [])}
    else:
        print("No 'Workspace Role' table; skipping role-based visibility checks.")
        return {"ok": True, "skipped": "no Workspace Role table"}

    public_with_roles = sorted(public & roles)
    all_ws = set(frappe.get_all("Workspace", pluck="name"))
    private = all_ws - public
    private_without_roles = sorted((private - roles) - allowed)

    ok = not (public_with_roles or private_without_roles)
    result = {"ok": ok, "public_with_roles": public_with_roles, "private_without_roles": private_without_roles}

    if not ok and raise_on_error:
        frappe.throw(
            "Workspace visibility invariants failed: "
            f"public_with_roles={public_with_roles}, private_without_roles={private_without_roles}"
        )

    print("Workspace visibility invariants look good." if ok else result)
    return result



def _remember_blueprint(slug: str):
    """Persist the chosen blueprint for this site so policy loading is automatic."""
    try:
        from frappe.installer import update_site_config  # newer stacks
    except Exception:
        from frappe.utils.install import update_site_config  # older stacks

    # Save which blueprint this site is using
    update_site_config("zanaverse_onboarding_blueprint", slug)

    # Also pin an exact policy path if it exists (handy when multiple policies exist)
    app_root = frappe.get_app_path("zanaverse_onboarding")
    policy_path = os.path.join(app_root, "blueprints", slug, "policy.yaml")
    if os.path.exists(policy_path):
        update_site_config("zanaverse_onboarding_policy_path", policy_path)


@frappe.whitelist()
def verify_letterheads(bp: str = "mtc") -> dict:
    out = {
        "files": frappe.get_all("File",
                 filters={"file_url":["like","/files/letterheads/%"]},
                 fields=["file_url","is_private"]),
        "letterheads": frappe.get_all("Letter Head",
                        fields=["name","image","is_default","disabled"]),
        "companies": frappe.get_all("Company", fields=["name","default_letter_head"]),
        "global_default": frappe.get_all("Letter Head",
                           filters={"is_default":1, "disabled":0},
                           fields=["name","image"]),
    }
    print(out)
    return out

# === Zanaverse: disable Module Profile support (migrated to Workspaces fixtures) ===
def _apply_module_profiles_from_yaml(bp: str):  # noqa: F811 (intentional override)
    """No-op: Module Profiles are deprecated in Zanaverse onboarding.
    We use role-scoped Workspaces (fixtures) + role profiles + default_workspace."""
    return
