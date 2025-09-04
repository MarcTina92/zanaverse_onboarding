import os, json, glob
import frappe
from .letterheads import ensure_letterheads as _ensure_letterheads

try:
    from frappe.exceptions import DuplicateEntryError
except Exception:
    # Fallback for older stacks; or just leave DuplicateEntryError undefined if you prefer
    class DuplicateEntryError(Exception): ...
try:
    import yaml
except Exception:
    yaml = None
import click

# NEW: import the helper you created
from zanaverse_onboarding.provisioning.restrict_standard_workspaces import (
    restrict_standard_workspaces,
)


# Use the app root (stable across benches)
APP_ROOT = frappe.get_app_path("zanaverse_onboarding")
BP_ROOT  = os.path.join(APP_ROOT, "blueprints")

def _read_yaml(path):
    if not yaml or not os.path.exists(path):
        return {"docs": []}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "docs" not in data:
        data["docs"] = []
    return data

def _ensure_name(d: dict) -> dict:
    # Ensure every doc has a stable 'name'. Fallbacks for common doctypes.# 
    if d.get("name"):
        return d
    # Generic fallback
    if d.get("title"):
        d["name"] = d["title"]
    # Sales Taxes and Charges Template => prefer 'Title - Company' as a deterministic name
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
    # ✅ add this:
    if dt == "Role Profile":
        d.setdefault("role_profile", d.get("name"))
    return d

def _resolve_tax_template_name(d: dict) -> str | None:
    # Find existing Sales Tax Template by (title, company) or common name patterns.# 
    if d.get("doctype") != "Sales Taxes and Charges Template":
        return None
    title = d.get("title") or d.get("name")
    if not title:
        return None
    company = d.get("company")
    # 1) Exact field match on title (+ company)
    filters = {"title": title}
    if company:
        filters["company"] = company
    existing = frappe.db.get_value("Sales Taxes and Charges Template", filters, "name")
    if existing:
        return existing
    # 2) Common name patterns
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

def _merge_docs(doc_sets):
    merged = {}
    for ds in doc_sets:
        for d in ds.get("docs", []):
            d = dict(d)  # copy
            d = _ensure_name(d)
            d = _ensure_required_fields(d)
            doctype, name = d.get("doctype"), d.get("name")
            if not doctype or not name:
                frappe.throw(f"Each doc needs doctype+name (or title): {d}")
            key = (doctype, name)
            base = merged.get(key, {})
            merged[key] = {**base, **d}
    return list(merged.values())

# --- Workspace comparison normalizers (make provisioning idempotent) ----------
# keep only meaningful keys from Workspace child rows, and sort for stability
_WS_KEEP = {
    "type","label","icon","description","hidden",
    "link_type","link_to","url","doc_view","kanban_board",
    "report_ref_doctype","is_query_report","dependencies",
    "only_for","onboard","color","format","stats_filter","link_count"
}
_WS_CHILD_TABLES = ("links","shortcuts","charts","number_cards","quick_lists","custom_blocks")

def _coerce_bool_int(v):
    # Frappe often stores 0/1; YAML may render as True/False. Normalize.
    if isinstance(v, bool):
        return 1 if v else 0
    return v

def _is_trivial(v):
    # treat these as "absent" for compare purposes
    return v is None or v == "" or v == 0 or v == [] or v == {}

def _clean_row(row: dict) -> dict:
    out = {}
    for k in _WS_KEEP:
        if k in row:
            v = _coerce_bool_int(row.get(k))
            if not _is_trivial(v):
                # normalize strings (strip)
                if isinstance(v, str):
                    v = v.strip()
                    if not v:
                        continue
                out[k] = v
    return out

def _normalize_workspace_rows(rows):
    cleaned = [_clean_row(r or {}) for r in (rows or [])]
    # drop empties
    cleaned = [r for r in cleaned if r]
    # stable ordering for equality checks
    cleaned.sort(key=lambda x: (
        x.get("type",""), x.get("label",""),
        x.get("link_type",""), x.get("link_to",""),
        x.get("doc_view",""), x.get("url","")
    ))
    return cleaned

def _normalize_for_compare(d):
    d = dict(d)
    d.pop("content", None)
    if d.get("doctype") == "Workspace":
        # prevent churn from server-side changes
        d.pop("sequence_id", None)
        for t in _WS_CHILD_TABLES:
            if t in d:
                d[t] = _normalize_workspace_rows(d.get(t))
    return d


def _collect_blueprint(client_slug):
    # Only load files from the chosen blueprint; do NOT include shared templates
    client_dir = os.path.join(BP_ROOT, client_slug)
    client_files = sorted(glob.glob(os.path.join(client_dir, "*.yaml")))
    doc_sets = [_read_yaml(p) for p in client_files]
    docs = _merge_docs(doc_sets)
    assets_dir = os.path.join(client_dir, "assets")
    return docs, assets_dir
# --- Module helpers (ensure Module Def exists before saving Workspaces) ------
def _ensure_module_def(module: str, app_default: str = "zanaverse_onboarding"):
    if frappe.db.exists("Module Def", {"module_name": module}):
        return
    # Module Def has either 'app_name' (newer) or 'app' (older) depending on stack
    fields = {df.fieldname for df in frappe.get_meta("Module Def").fields}
    payload = {"doctype": "Module Def", "module_name": module}
    if "app_name" in fields:
        payload["app_name"] = app_default
    elif "app" in fields:
        payload["app"] = app_default
    else:
        # very old stacks; if neither field exists just insert minimal payload
        pass
    frappe.get_doc(payload).insert(ignore_permissions=True)

def _ensure_modules_for_docs(docs, app_default: str = "zanaverse_onboarding"):
    # Find every Workspace in the blueprint that sets a module and ensure it exists
    modules = sorted({
        d.get("module") for d in docs
        if d.get("doctype") == "Workspace" and d.get("module")
    })
    for m in modules:
        _ensure_module_def(m, app_default)


def _plan_changes(docs):
    plan = {"create": [], "update": [], "noop": []}
    for d in docs:
        d = dict(d)
        doctype, name = d["doctype"], d["name"]

        # Special resolution for Sales Taxes and Charges Template
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
            # normalize both sides before comparing (important for Workspaces)
            cur_n = _normalize_for_compare(current)
            new_n = _normalize_for_compare(d)

            delta = {
                k: v for k, v in new_n.items()
                if k not in ("doctype","name") and cur_n.get(k) != v
            }

            if delta:
                plan["update"].append({"doctype": doctype, "name": name, **delta})
            else:
                plan["noop"].append({"doctype": doctype, "name": name})
    return plan


def _apply_plan(plan):
    applied = {"created": [], "updated": []}
    for d in plan["create"]:
        payload = dict(d)
        # Let ERPNext autoname Sales Tax Template; if dup, fall back to update
        if payload["doctype"] == "Sales Taxes and Charges Template":
            payload.pop("name", None)
        try:
            doc = frappe.get_doc(payload)
            doc.insert(ignore_permissions=True)
            applied["created"].append((payload["doctype"], doc.name))
        except DuplicateEntryError:
            if payload["doctype"] == "Sales Taxes and Charges Template":
                existing = _resolve_tax_template_name(d)  # use original d for title/company
                if existing:
                    doc = frappe.get_doc(payload["doctype"], existing)
                    for k, v in d.items():
                        if k in ("doctype","name"): continue
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
            if k in ("doctype","name"): continue
            doc.set(k, v)
        doc.save(ignore_permissions=True)
        applied["updated"].append((d["doctype"], d["name"]))
    frappe.db.commit()
    return applied

def _ensure_baselines():
    # Seed minimal masters ERPNext expects so Company creation never fails.# 
    if frappe.db.exists("DocType", "Warehouse Type"):
        needed = ["Transit", "Finished Goods", "Work In Progress", "Stores"]
        for wt in needed:
            if not frappe.db.exists("Warehouse Type", wt):
                # tolerate fieldname differences across versions
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

# --- simple YAML loader for roles/users/companies/brands ---
def _load_simple_yaml(bp, filename):
    path = os.path.join(BP_ROOT, bp, filename)
    if not yaml or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# --- ensure Brand Link custom field on common doctypes ---
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
    "Lead","Opportunity","Customer","Quotation","Sales Order",
    "Project","Task","Employee","Job Applicant","Job Opening"
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


# --- companies & brands from simple YAML files ---
def _apply_companies_from_yaml(bp):
    data = _load_simple_yaml(bp, "companies.yaml")
    for c in (data.get("companies") or []):
        name = c.get("company_name")
        if not name:
            continue
        if frappe.db.exists("Company", name):
            doc = frappe.get_doc("Company", name)
            if c.get("abbr"): doc.abbr = c["abbr"]
            if c.get("default_currency"): doc.default_currency = c["default_currency"]
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "Company",
                "company_name": name,
                "abbr": c.get("abbr"),
                "default_currency": c.get("default_currency")
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

# --- roles.yaml cloner (union-only, safe) ------------------------------------
from typing import Dict, Any, Tuple, List

def _ensure_role_doc(role_name: str, desk_access: bool | None, dry_run: bool) -> tuple[bool, bool]:
    """Return (created, updated) for Role doc."""
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
    """All fields we may set on Custom DocPerm."""
    meta = frappe.get_meta("Custom DocPerm", cached=True)
    base = {"parent", "parenttype", "parentfield", "role", "permlevel"}
    return base | {df.fieldname for df in meta.fields}


def _perm_key(row: Dict[str, Any]) -> Tuple[str, int]:
    return (row.get("parent"), int(row.get("permlevel") or 0))


def _fetch_base_perms(base_role: str) -> List[Dict[str, Any]]:
    """Stock DocPerm + Custom DocPerm for the given base role."""
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
    """OR/union boolean flags (read, write, create, etc.). Return True if any change."""
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
    """
    Create/update custom roles from blueprints/<bp>/roles.yaml
    and union their DocType permissions from the listed base roles.

    Example:
      bench --site <yoursite> execute zanaverse_onboarding.cli.clone_roles_from_yaml \
        --kwargs "{'blueprint':'mtc','dry_run':1}"
    """
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
        target = row.get("name") or row.get("role")  # support either key
        bases = row.get("clone_from") or []
        if isinstance(bases, str):
            bases = [bases]
        desk_access = row.get("desk_access", None)

        if not target or not bases:
            frappe.throw(f"Invalid roles.yaml row (need name & clone_from): {row}")

        # 1) ensure Role exists / desk flag set
        created, updated = _ensure_role_doc(target, desk_access, dry_run=bool(dry_run))
        if created:
            summary["created_roles"].append(target)
        if updated:
            summary["updated_roles"].append(target)

        # 2) existing target custom perms by (doctype, permlevel)
        existing: dict[tuple[str, int], dict] = {}
        rows = frappe.get_all("Custom DocPerm", filters={"role": target}, fields=["*"]) or []
        for r in rows:
            existing[_perm_key(r)] = dict(r)

        # 3) collect source perms from all base roles
        src_rows: list[dict] = []
        for base in bases:
            if frappe.db.exists("Role", base):
                src_rows.extend(_fetch_base_perms(base))

        # 4) union into target
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
# --- CLI wrapper -------------------------------------------------------------



# --- roles from roles.yaml ---
from frappe.permissions import add_permission

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

# --- lightweight Role→DocType permission matrix (tune later) ---
_RP_MATRIX = [
    {"doctype":"Lead",         "roles":["Sales Executive","Sales Manager","Marketing Executive"]},
    {"doctype":"Opportunity",  "roles":["Sales Executive","Sales Manager"]},
    {"doctype":"Customer",     "roles":["Sales Executive","Sales Manager"]},
    {"doctype":"Quotation",    "roles":["Sales Executive","Sales Manager"]},
    {"doctype":"Sales Order",  "roles":["Sales Manager"]},
    {"doctype":"Project",      "roles":["Research Staff","Sales Manager"]},
    {"doctype":"Task",         "roles":["Research Staff","Sales Manager"]},
    {"doctype":"Employee",     "roles":["HR Assistant","HR Manager"]},
    {"doctype":"Job Applicant","roles":["HR Assistant","HR Manager"]},
    {"doctype":"Job Opening",  "roles":["HR Assistant","HR Manager"]},
]

def _ensure_docperm_row(dt, role, permlevel=0):
    # make sure a DocPerm child row exists
    name = frappe.db.get_value(
        "DocPerm",
        {"parent": dt, "role": role, "permlevel": permlevel},
        "name",
    )
    if not name:
        # create a base row
        add_permission(dt, role, permlevel=permlevel)
        name = frappe.db.get_value(
            "DocPerm",
            {"parent": dt, "role": role, "permlevel": permlevel},
            "name",
        )
    return name

def _docperm_supports_apply_user_permissions() -> bool:
    try:
        # works across versions; returns [] if column missing
        return bool(frappe.db.sql("SHOW COLUMNS FROM `tabDocPerm` LIKE 'apply_user_permissions'"))
    except Exception:
        return False

def _apply_role_permissions():
    has_apply = _docperm_supports_apply_user_permissions()
    for row in _RP_MATRIX:
        dt = row["doctype"]
        for role in row["roles"]:
            name = _ensure_docperm_row(dt, role, permlevel=0)
            if not name:
                continue
            # basic CRUD
            for col in ("read", "write", "create"):
                frappe.db.set_value("DocPerm", name, col, 1)
            # only set this if the column exists on your version
            if has_apply:
                frappe.db.set_value("DocPerm", name, "apply_user_permissions", 1)


# --- users + scoping from users.yaml ---
def _ensure_user_doc(u, defaults):
    email = u["email"]
    user = frappe.get_doc("User", email) if frappe.db.exists("User", email) else frappe.new_doc("User")

    # basics
    user.email = email
    user.first_name = u.get("full_name") or email.split("@")[0]
    user.language = u.get("language") or defaults.get("language")
    user.time_zone = u.get("time_zone") or defaults.get("time_zone")
    user.enabled = 1
    user.send_welcome_email = 0

    # System vs Website user
    is_desk = bool(u.get("is_desk_user", True))
    user.user_type = "System User" if is_desk else "Website User"

    # Persist core fields early (creates the user if new)
    user.save(ignore_permissions=True)

    # ---- gather roles from role_profile(s) + explicit roles ----
    # Accept either role_profile: "Name" or role_profiles: ["A","B"]
    profiles = []
    if u.get("role_profile"):
        profiles.append(u["role_profile"])
    if u.get("role_profiles"):
        profiles.extend(u["role_profiles"] if isinstance(u["role_profiles"], list) else [u["role_profiles"]])

    # Union roles from profiles
    profile_roles = set()
    for rp_name in profiles:
        if not rp_name:
            continue
        if not frappe.db.exists("Role Profile", rp_name):
            frappe.log_error(f"Role Profile not found: {rp_name}", "provision users")
            continue
        rp = frappe.get_doc("Role Profile", rp_name)
        for rr in rp.roles or []:
            if rr.role:
                profile_roles.add(rr.role)

    # Add any explicit extra roles in YAML
    extra_roles = set(u.get("roles") or [])
    target_roles = profile_roles | extra_roles

    # Current roles on user
    have = {r.role for r in user.roles}

    # Add missing roles (union-only; we don't remove anything)
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

@frappe.whitelist()
def provision(blueprint: str, dry_run: int = 0, commit_sha: str = None, harden_workspaces: int = 1):
    """Provision client blueprint (supports dry_run, commit_sha, workspace hardening)."""
    site = frappe.local.site
    dry_run = int(dry_run or 0)
    harden = int(harden_workspaces or 0)

    # Collect docs and exclude Role Profiles from the generic plan (handled separately)
    docs, assets_dir = _collect_blueprint(blueprint)
    docs = [d for d in docs if (d.get("doctype") or "") != "Role Profile"]

    plan = _plan_changes(docs)
    summary_text = f"Create: {len(plan['create'])}, Update: {len(plan['update'])}, Noop: {len(plan['noop'])}"

    # Default summaries
    ws_summary = {}
    applied = {"created": [], "updated": []}

    if dry_run:
        # Run workspace hardening in dry-run mode too (so you can preview)
        try:
            if harden:
                ws_summary = restrict_standard_workspaces(
                    dry_run=True,
                    include_modules=None,                 # e.g., ("CRM","HR","Accounts")
                    exclude_names=("Zanaverse Home",),    # keep this one public
                    force=False,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Workspace hardening (dry-run) failed")

        _safe_log(site, blueprint, True, summary_text, plan, "DRY-RUN", commit_sha)
        payload = {"summary": summary_text, "plan": plan, "workspace_hardening": ws_summary}
        print(json.dumps(payload, indent=2))
        return payload

    # --- APPLY PATH ----------------------------------------------------------
    _ensure_baselines()

    # NEW: make sure any modules referenced by Workspace docs (e.g. "Zanaverse") exist
    _ensure_modules_for_docs(docs, app_default="zanaverse_onboarding")

    applied = _apply_plan(plan)

    # Simple YAML sections
    _apply_companies_from_yaml(blueprint)
    _apply_brands_from_yaml(blueprint)
    _apply_brand_custom_fields_if_needed()

    # ⛔ keep role cloning OFF unless you truly want to generate custom roles
    # clone_roles_from_yaml(blueprint=blueprint, dry_run=0)

    # ✅ Role Profiles (safe, idempotent)
    _apply_role_profiles_from_yaml(blueprint, union_only=True)

    # ✅ Users (can reference role_profile / role_profiles)
    _apply_users_from_yaml(blueprint)

    # --- Harden role-less public Workspaces (policy) -------------------------
    try:
        if harden:
            ws_summary = restrict_standard_workspaces(
                dry_run=False,
                include_modules=None,
                exclude_names=("Zanaverse Home",),
                force=False,
            )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Workspace hardening failed")

    # Assets (letterheads, etc.)
    _ensure_letterheads(docs, assets_dir)

    frappe.db.commit()
    _safe_log(site, blueprint, False, summary_text, plan, "SUCCESS", commit_sha)

    payload = {"summary": summary_text, "applied": applied, "workspace_hardening": ws_summary}
    print(json.dumps(payload, indent=2))
    return payload


def _remember_blueprint(slug: str):
    """Persist the chosen blueprint for this site so policy loading is automatic."""
    try:
        from frappe.installer import update_site_config  # new-ish location
    except Exception:
        from frappe.utils.install import update_site_config  # fallback on older stacks

    update_site_config("zanaverse_onboarding_blueprint", slug)

    # Optionally also pin the exact policy file path (works even if multiple exist)
    app_root = frappe.get_app_path("zanaverse_onboarding")
    policy_path = os.path.join(app_root, "blueprints", slug, "policy.yaml")
    if os.path.exists(policy_path):
        update_site_config("zanaverse_onboarding_policy_path", policy_path)


def _apply_role_profiles_from_yaml(bp, union_only=True):
    data = _load_simple_yaml(bp, "role_profiles.yaml")
    profiles = data.get("role_profiles") or []

    created = 0
    updated = 0

    # Avoid queue_action/locks on Role Profile during provisioning
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
            if add:
                for r in add:
                    doc.append("roles", {"role": r})

            if not union_only:
                keep = set(roles)
                doc.roles = [row for row in doc.roles if row.role in keep]

            # Save without triggering heavy queue side-effects
            doc.save(ignore_permissions=True)

            if is_new:
                created += 1
            else:
                # count as updated only if something changed
                if add or (not union_only and have - set(roles)):
                    updated += 1
    finally:
        frappe.flags.in_migrate = old_flag


    frappe.db.commit()
    print(f"Applied Role Profiles: created={created}, updated={updated}, total={len(profiles)}")
    return {"ok": True, "created": created, "updated": updated, "total": len(profiles)}


# --- Doctor: policy ↔ meta sanity check --------------------------------------


@click.command("zv-doctor")
@click.option("--site", "site_name", help="Frappe site to use (bench also accepts --site).")
def doctor(site_name: str | None = None):
    """Sanity-check policy.yaml against DocType metadata and show registered PQCs."""
    import os
    import frappe

    # Ensure there's a site context; bench may NOT initialize it for custom commands.
    site = getattr(frappe.local, "site", None) or site_name or os.environ.get("FRAPPE_SITE")
    if not site:
        click.echo("No site context. Run as: bench --site <your-site> zv-doctor")
        return

    did_connect = False
    if getattr(frappe.local, "site", None) != site:
        # Explicitly init + connect so frappe.local.site and DB are ready
        frappe.init(site=site)
        frappe.connect()
        did_connect = True

    try:
        # Import AFTER site context exists (permissions.py reads frappe.local.site on import)
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
