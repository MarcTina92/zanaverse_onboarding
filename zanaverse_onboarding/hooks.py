# hooks.py
from __future__ import annotations

app_name = "zanaverse_onboarding"
app_title = "Zanaverse Onboarding"
app_publisher = "MarcTina"
app_description = "Client onboarding with blueprints"
app_email = "info@marctinaconsultancy.com"
app_license = "mit"

# ---------------------------
# Permission Query Conditions
# ---------------------------
# Build PQC map from your policy at import-time, but fail safe if no site context yet.
try:
    from zanaverse_onboarding import permissions as _perm
    _policy = _perm._load_policy()
    permission_query_conditions = {
        dt: f"zanaverse_onboarding.permissions.pqc_{dt.lower().replace(' ', '_')}"
        for dt, cfg in (_policy.get("pqc_doctypes") or {}).items()
        if cfg and cfg.get("enabled") and hasattr(_perm, f"pqc_{dt.lower().replace(' ', '_')}")
    }
except Exception:
    permission_query_conditions = {}

# Optional per-doctype has_permission hooks
has_permission = {
    "Employee": "zanaverse_onboarding.permissions.has_permission_employee",
}

# --------------
# Migrate Hooks
# --------------
# Conditionally include a before_migrate patch if it exists.
try:
    import importlib
    importlib.import_module("zanaverse_onboarding.patches.ensure_module_and_doctype")
    before_migrate = ["zanaverse_onboarding.patches.ensure_module_and_doctype.execute"]
except Exception:
    before_migrate = []

# Always run our safe, idempotent workspace normalizer after migrate.
after_migrate = [
    "zanaverse_onboarding.cli.apply_default_workspaces_after_migrate",
    "zanaverse_onboarding.cli.verify_workspace_visibility_invariants",
]

# If you also ship install hooks, register them only if present.
try:
    from zanaverse_onboarding import install as _install  # type: ignore
    if hasattr(_install, "after_migrate"):
        after_migrate.append("zanaverse_onboarding.install.after_migrate")
    if hasattr(_install, "after_install"):
        after_install = "zanaverse_onboarding.install.after_install"
except Exception:
    pass

# ---------------------------
# (Leave other sections empty)
# ---------------------------
# Add desk/web assets, schedulers, overrides, etc. here when you need them.
