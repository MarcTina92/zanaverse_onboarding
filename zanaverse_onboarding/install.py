import frappe


def _reload_schemas():
    """Reload lightweight doctypes that provisioning may touch (safe if missing)."""
    try:
        frappe.reload_doc("zanaverse_onboarding", "doctype", "provision_log")
    except Exception:
        # ok if the doctype isn't present yet
        frappe.db.rollback()


def _get_blueprint_default() -> str:
    """Read preferred blueprint from site_config; fallback to 'mtc'."""
    try:
        conf = frappe.get_conf() or {}
        return conf.get("zanaverse_onboarding_blueprint") or "mtc"
    except Exception:
        return "mtc"


def _run_once(blueprint: str = "mtc", harden: int = 0):
    """
    Idempotent bootstrap:
    - remembers chosen blueprint in site_config
    - applies blueprint YAML via provision()
    - optionally hardens stock workspaces (disabled by default)
    """
    from zanaverse_onboarding.cli import provision, _remember_blueprint

    # remember the blueprint so future runs/migrations stay consistent
    try:
        _remember_blueprint(blueprint)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ZV Onboarding: remember_blueprint failed")
        frappe.db.rollback()

    # apply provisioning (creates Module Defs for any Workspace.module, applies YAML)
    try:
        provision(
            blueprint=blueprint,
            dry_run=0,
            commit_sha=None,
            # keep hardening OFF unless explicitly enabled
            harden_workspaces=int(harden or 0),
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ZV Onboarding: provision failed")
        frappe.db.rollback()


def after_install():
    """Runs on `bench --site <site> install-app zanaverse_onboarding`."""
    _reload_schemas()
    # keep hardening OFF by default
    _run_once(blueprint=_get_blueprint_default(), harden=0)  # <- OFF


def after_migrate():
    """Keep things consistent after migrations."""
    _reload_schemas()
    bp = _get_blueprint_default()
    # keep hardening OFF by default
    _run_once(blueprint=_get_blueprint_default(), harden=0)  # <- OFF


@frappe.whitelist()
def bootstrap(blueprint: str = "mtc", harden: int = 0):
    """
    Manual helper you can run anytime, e.g.:
      bench --site your.site execute zanaverse_onboarding.install.bootstrap \
        --kwargs '{"blueprint":"mtc","harden":1}'
    """
    _run_once(blueprint=blueprint, harden=int(harden or 0))
    return {"ok": True, "blueprint": blueprint, "harden": int(harden or 0)}
