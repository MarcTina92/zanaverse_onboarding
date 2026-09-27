# hooks.py
from __future__ import annotations

app_name = "zanaverse_onboarding"
app_title = "Zanaverse Onboarding"
app_publisher = "MarcTina"
app_description = "Client onboarding with blueprints"
app_email = "info@marctinaconsultancy.com"
app_license = "mit"

# ---------------------------------------------------------------------------
# zanaverse_onboarding is the provisioning toolkit (blueprint engine:
# zanaverse_onboarding.blueprint_apply). It carries NO runtime behaviour:
# runtime features live in zanaverse_config behind per-site switches
# (Zanaverse Settings), switched on by each site's blueprint.
#
# TEMPORARY: the Timesheet rule below stays until the platform Timesheet
# feature (Phase 5) replaces it in the same deploy.
# ---------------------------------------------------------------------------
permission_query_conditions = {
    "Timesheet": "zanaverse_onboarding.permissions.pqc_timesheet",
}

has_permission = {
    "Timesheet": "zanaverse_onboarding.permissions.has_permission_timesheet",
}

# Install housekeeping for this app's own module and doctypes.
before_migrate = ["zanaverse_onboarding.patches.ensure_module_and_doctype.execute"]
after_install = "zanaverse_onboarding.install.after_install"
