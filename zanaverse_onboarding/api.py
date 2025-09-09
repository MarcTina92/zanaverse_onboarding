cd ~/frappe-bench/apps/zanaverse_onboarding

mkdir -p zanaverse_onboarding

cat > zanaverse_onboarding/api.py <<'PY'
import os, sys, json, importlib, datetime
import frappe

@frappe.whitelist(allow_guest=True)
def health():
    """
    GET /api/method/zanaverse_onboarding.api.health
    Returns app import status, version, assets presence, site, and environment info.
    """
    out = {}
    out["ts_utc"] = datetime.datetime.utcnow().isoformat() + "Z"
    out["site"] = getattr(frappe.local, "site", None)
    out["python"] = sys.executable
    out["cwd"] = os.getcwd()

    # version
    try:
        from . import __version__
        out["version"] = __version__
    except Exception:
        out["version"] = None

    # import hooks
    try:
        m = importlib.import_module("zanaverse_onboarding.hooks")
        out["import_ok"] = True
        out["hooks_file"] = getattr(m, "__file__", None)
    except Exception as e:
        out["import_ok"] = False
        out["import_error"] = repr(e)

    # installed apps
    try:
        out["installed_apps"] = frappe.get_installed_apps()
    except Exception as e:
        out["installed_apps_error"] = repr(e)

    # built assets present?
    try:
        app_path = frappe.get_app_path("zanaverse_onboarding")
        js_dir  = os.path.join(app_path, "public", "dist", "js")
        css_dir = os.path.join(app_path, "public", "dist", "css")
        out["assets_present"] = {
            "js":  os.path.isdir(js_dir)  and any((f.endswith(".js")  for f in os.listdir(js_dir)  or [])),
            "css": os.path.isdir(css_dir) and any((f.endswith(".css") for f in os.listdir(css_dir) or [])),
        }
    except Exception as e:
        out["assets_present_error"] = repr(e)

    frappe.local.response["type"] = "json"
    return out
PY
