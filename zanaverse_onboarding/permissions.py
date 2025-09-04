from __future__ import annotations
import os
import frappe

# yaml is optional; we fallback to built-in defaults if missing / unreadable
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # policy.yaml loading will be skipped

# ---------- policy loading (optional, cached per request) ----------

import fnmatch

def _read_sites_map() -> dict:
    """Read blueprints/_sites.yaml and return either 'map' or 'sites' dict."""
    try:
        app_root = frappe.get_app_path("zanaverse_onboarding")
        path = os.path.join(app_root, "blueprints", "_sites.yaml")
        if not (yaml and os.path.exists(path)):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # support both styles
        return (data.get("map") or data.get("sites") or {}) or {}
    except Exception:
        return {}

def _slug_from_repo_sites_map(site: str) -> str | None:
    m = _read_sites_map()
    if not m:
        return None

    # Style B: direct site -> slug
    if isinstance(next(iter(m.values()), None), str):   # {"site": "slug"}
        return m.get(site)

    # Style A: {"slug": ["pattern1", ...]}
    for slug, patterns in m.items():
        for pat in (patterns or []):
            if fnmatch.fnmatch(site, pat):
                return slug
    return None

def _policy_path_candidates() -> list[str]:
    app_root = frappe.get_app_path("zanaverse_onboarding")
    conf = getattr(frappe.local, "conf", {}) or {}

    explicit = conf.get("zanaverse_onboarding_policy_path")
    if explicit:
        return [explicit]

    candidates = [os.path.join(app_root, "blueprints", "policy.yaml")]

    slug = conf.get("zanaverse_onboarding_blueprint")
    if not slug:
        # Fallback to repo mapping if site_config doesn’t set a slug
        slug = _slug_from_repo_sites_map(frappe.local.site)

    if slug:
        candidates.append(os.path.join(app_root, "blueprints", slug, "policy.yaml"))

    return candidates



def _load_policy() -> dict:
    """Load + cache policy: defaults → global file → client file (layered)."""
    cached = getattr(frappe.local, "_zv_policy", None)
    if cached is not None:
        return cached

    # ---- in-code defaults so things are safe even with no YAML present ----
    merged = {
        "sensitive_roles": {
            "Employee": ["HR Manager", "HR Assistant"],
        },
        "strict_default_deny": False,
        "pqc_doctypes": {
            # CRM / Sales
            "Lead":            {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Opportunity":     {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Customer":        {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Quotation":       {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Sales Order":     {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            # Projects / HR
            "Project":         {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Task":            {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Employee":        {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Job Applicant":   {"enabled": True,  "company_field": "company", "brand_field": "brand"},
            "Job Opening":     {"enabled": True,  "company_field": "company", "brand_field": "brand"},
        },
    }

    # No PyYAML available → stick to defaults
    if not yaml:
        frappe.local._zv_policy = merged
        return merged

    # Apply each existing YAML file in order (global then client), layering keys
    for path in _policy_path_candidates():
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                # shallow merge for top-level keys
                merged = {**merged, **data}

                # deep merge for maps we know about
                for k in ("pqc_doctypes", "sensitive_roles"):
                    if k in data:
                        merged[k] = {**merged.get(k, {}), **(data.get(k) or {})}
        except Exception:
            # ignore bad files; keep going with what we have
            frappe.log_error(frappe.get_traceback(), f"policy load failed: {path}")
            continue

    frappe.local._zv_policy = merged
    return merged


# ---------- helpers ----------

def _policy_for_doctype(doctype: str) -> dict:
    pol = _load_policy()
    return (pol.get("pqc_doctypes") or {}).get(doctype, {}) or {}

def _sensitive_roles_for(doctype: str) -> set[str]:
    pol = _load_policy()
    roles = (pol.get("sensitive_roles") or {}).get(doctype, []) or []
    return set(roles)

def _strict_default_deny() -> bool:
    pol = _load_policy()
    return bool(pol.get("strict_default_deny"))

def _allowed(user: str, doctype: str) -> set[str]:
    """Get all allowed values for a given doctype from User Permission."""
    cache_key = f"_up_{user}_{doctype}"
    cached = getattr(frappe.local, cache_key, None)
    if cached is not None:
        return cached

    vals = set(
        frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": doctype},
            pluck="for_value",
        ) or []
    )
    setattr(frappe.local, cache_key, vals)
    return vals

def user_scope(user: str | None = None) -> dict[str, set[str]]:
    user = user or frappe.session.user
    return {"companies": _allowed(user, "Company"), "brands": _allowed(user, "Brand")}

def _has_field(doctype: str, fieldname: str) -> bool:
    if not fieldname:
        return False
    meta = frappe.get_meta(doctype, cached=True)
    return meta.has_field(fieldname)

def _inlist(values: set[str]) -> str:
    if not values:
        return "()"
    esc = ", ".join(frappe.db.escape(v) for v in values)
    return f"({esc})"

def _roles_for(user: str) -> set[str]:
    """Cached roles for this request to avoid repeated DB hits."""
    key = f"_roles_{user}"
    cached = getattr(frappe.local, key, None)
    if cached is None:
        cached = set(frappe.get_roles(user))
        setattr(frappe.local, key, cached)
    return cached

# ---------- Autogenerate PQC wrappers for any doctypes in policy.yaml ----------

import sys, re

def _slug_for_fn(doctype: str) -> str:
    # sanitize to a valid python identifier: lower + non-alnum -> _
    s = doctype.lower().strip().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"pqc_{s or 'unknown'}"

def _autogen_pqc_wrappers():
    pol = _load_policy()
    pqc_map = pol.get("pqc_doctypes") or {}
    mod = sys.modules[__name__]

    for dt, cfg in pqc_map.items():
        if not (cfg and cfg.get("enabled")):
            continue
        fn_name = _slug_for_fn(dt)

        # don't override explicit wrappers (e.g., pqc_project / pqc_task)
        if hasattr(mod, fn_name):
            continue

        # capture dt by default arg to avoid late-binding
        def _make(dt_name: str):
            def _wrapper(user):
                return _pqc_base_from_policy(dt_name, user)
            _wrapper.__name__ = fn_name
            return _wrapper

        setattr(mod, fn_name, _make(dt))

# Run once at import-time so hooks can see the generated functions
#_autogen_pqc_wrappers(). - remove later



# ---------- generic PQC builder ----------

def _pqc_bypass(user: str | None) -> bool:
    user = user or frappe.session.user
    pol = _load_policy()
    bypass = set(pol.get("pqc_bypass_roles") or [])
    if not bypass:
        return False
    return bool(set(_roles_for(user)) & bypass)


def pqc_generic(
    doctype: str,
    company_field: str = "company",
    brand_field: str = "brand",
    user: str | None = None,
) -> str:
    """
    Permission Query Condition: appended to WHERE for list/link queries.
    We AND the Company and Brand constraints when both are present.
    """
    # ✅ bypass first (avoid extra DB work)
    if _pqc_bypass(user):
        return ""  # full visibility, no filter

    scope = user_scope(user)
    conds: list[str] = []

    if scope["companies"] and _has_field(doctype, company_field):
        conds.append(f"`tab{doctype}`.`{company_field}` IN {_inlist(scope['companies'])}")

    if scope["brands"] and _has_field(doctype, brand_field):
        conds.append(f"`tab{doctype}`.`{brand_field}` IN {_inlist(scope['brands'])}")

    if conds:
        return " AND ".join(conds)

    return "1=0" if _strict_default_deny() else ""

def _pqc_base_from_policy(doctype: str, user: str | None) -> str:
    cfg = _policy_for_doctype(doctype)
    if not cfg or not cfg.get("enabled"):
        return ""
    return pqc_generic(
        doctype,
        company_field=cfg.get("company_field") or "company",
        brand_field=cfg.get("brand_field") or "brand",
        user=user,
    )



# ---------- PQC wrappers registered in hooks.py ----------

def pqc_lead(user):          return _pqc_base_from_policy("Lead", user)
def pqc_opportunity(user):   return _pqc_base_from_policy("Opportunity", user)
def pqc_customer(user):      return _pqc_base_from_policy("Customer", user)
def pqc_quotation(user):     return _pqc_base_from_policy("Quotation", user)
def pqc_sales_order(user):   return _pqc_base_from_policy("Sales Order", user)
def pqc_job_applicant(user): return _pqc_base_from_policy("Job Applicant", user)
def pqc_job_opening(user):   return _pqc_base_from_policy("Job Opening", user)
def pqc_employee(user):      return _pqc_base_from_policy("Employee", user)  # coarse list filter


# ---------- Collaboration-aware PQCs for Project / Task ----------

def _exists_project_membership(user: str) -> str:
    u = frappe.db.escape(user)
    # Child table "Project User" has a "user" field
    return f"""exists(
        select 1
        from `tabProject User` pu
        where pu.parent = `tabProject`.`name`
          and pu.parenttype = 'Project'
          and pu.user = {u}
    )"""

def pqc_project(user):
    if _pqc_bypass(user):
        return ""  # full visibility
    base = _pqc_base_from_policy("Project", user)
    members = _exists_project_membership(user)
    if base and members:
        return f"(({base}) OR {members})"
    return members or base or ""

def pqc_task(user):
    if _pqc_bypass(user):
        return ""  # full visibility
    base = _pqc_base_from_policy("Task", user)
    u = frappe.db.escape(user)
    members = f"""exists(
        select 1
        from `tabProject User` pu
        join `tabProject` p on p.name = `tabTask`.`project`
        where pu.parent = p.name
          and pu.parenttype = 'Project'
          and pu.user = {u}
    )"""
    assigned = f"""exists(
        select 1
        from `tabToDo` td
        where td.reference_type = 'Task'
          and td.reference_name = `tabTask`.`name`
          and td.allocated_to = {u}
    )"""
    conds = [c for c in [base, members, assigned] if c]
    return " OR ".join(f"({c})" for c in conds) if conds else ""


# ---------- Fine-grained has_permission for sensitive doctypes ----------

def has_permission_generic(doc, ptype, user, **kwargs):
    """
    Generic guard for sensitive doctypes listed in policy.yaml -> sensitive_roles.
    - If user's roles intersect configured sensitive roles for the doctype: allow.
    - Special case for Employee: a user may read their own Employee record (doc.user_id == user).
    - Otherwise: return False and let Frappe block.
    """
    # ✅ normalize user for safety
    user = user or getattr(frappe.session, "user", None) or "Guest"

    # ✅ optional: if you want PQC bypass roles to bypass these has_permission checks too
    if _pqc_bypass(user):
        return True

    roles_needed = _sensitive_roles_for(getattr(doc, "doctype", ""))
    if roles_needed and (_roles_for(user) & roles_needed):  # cached roles
        return True

    if doc.doctype == "Employee" and ptype == "read" and getattr(doc, "user_id", None) == user:
        return True

    return False


# Backward-compatible wrapper kept for your current hooks.py
def has_permission_employee(doc, ptype, user, **kwargs):
    return has_permission_generic(doc, ptype, user, **kwargs)


# ... all function defs incl. pqc_project / pqc_task ...

# Run once at import-time so hooks can see the generated functions
_autogen_pqc_wrappers()
