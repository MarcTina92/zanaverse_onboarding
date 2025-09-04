app_name = "zanaverse_onboarding"
app_title = "Zanaverse Onboarding"
app_publisher = "MarcTina"
app_description = "Client onboarding with blueprints"
app_email = "info@marctinaconsultancy.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "zanaverse_onboarding",
# 		"logo": "/assets/zanaverse_onboarding/logo.png",
# 		"title": "Zanaverse Onboarding",
# 		"route": "/zanaverse_onboarding",
# 		"has_permission": "zanaverse_onboarding.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/zanaverse_onboarding/css/zanaverse_onboarding.css"
# app_include_js = "/assets/zanaverse_onboarding/js/zanaverse_onboarding.js"

# include js, css files in header of web template
# web_include_css = "/assets/zanaverse_onboarding/css/zanaverse_onboarding.css"
# web_include_js = "/assets/zanaverse_onboarding/js/zanaverse_onboarding.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "zanaverse_onboarding/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "zanaverse_onboarding/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "zanaverse_onboarding.utils.jinja_methods",
# 	"filters": "zanaverse_onboarding.utils.jinja_filters"
# }

# Installation
# ------------
# before_install = "zanaverse_onboarding.install.before_install"
# after_install = "zanaverse_onboarding.install.after_install"

# Uninstallation
# ------------
# before_uninstall = "zanaverse_onboarding.uninstall.before_uninstall"
# after_uninstall = "zanaverse_onboarding.uninstall.after_uninstall"

# Integration Setup
# ------------------
# before_app_install = "zanaverse_onboarding.utils.before_app_install"
# after_app_install = "zanaverse_onboarding.utils.after_app_install"

# Integration Cleanup
# -------------------
# before_app_uninstall = "zanaverse_onboarding.utils.before_app_uninstall"
# after_app_uninstall = "zanaverse_onboarding.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# notification_config = "zanaverse_onboarding.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# ...rest of your hooks.py...

# DocType Class
# ---------------
# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------
# scheduler_events = {
# 	"all": ["zanaverse_onboarding.tasks.all"],
# 	"daily": ["zanaverse_onboarding.tasks.daily"],
# 	"hourly": ["zanaverse_onboarding.tasks.hourly"],
# 	"weekly": ["zanaverse_onboarding.tasks.weekly"],
# 	"monthly": ["zanaverse_onboarding.tasks.monthly"],
# }

# Testing
# -------
# before_tests = "zanaverse_onboarding.install.before_tests"

# Overriding Methods
# ------------------------------
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "zanaverse_onboarding.event.get_events"
# }
# override_doctype_dashboards = {
# 	"Task": "zanaverse_onboarding.task.get_dashboard_data"
# }

# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["zanaverse_onboarding.utils.before_request"]
# after_request = ["zanaverse_onboarding.utils.after_request"]

# Job Events
# ----------
# before_job = ["zanaverse_onboarding.utils.before_job"]
# after_job = ["zanaverse_onboarding.utils.after_job"]

# User Data Protection
# --------------------
# user_data_fields = [
# 	{"doctype": "{doctype_1}", "filter_by": "{filter_by}", "redact_fields": ["{field_1}", "{field_2}"], "partial": 1},
# 	{"doctype": "{doctype_2}", "filter_by": "{filter_by}", "partial": 1},
# 	{"doctype": "{doctype_3}", "strict": False},
# 	{"doctype": "{doctype_4}"}
# ]

# Authentication and authorization
# --------------------------------
# auth_hooks = ["zanaverse_onboarding.auth.validate"]

# export_python_type_annotations = True

# default_log_clearing_doctypes = {"Logging DocType Name": 30}

#Fixtures for roles exporting 
#fixtures = [
 #   {"doctype": "Role", "filters": [["name", "like", "mtc\\_%"]]},
 #   {"doctype": "Custom DocPerm", "filters": [["role", "like", "mtc\\_%"]]},
#]

# Permissions (policy-driven PQCs)
from zanaverse_onboarding import permissions as perm

_pol = perm._load_policy()
permission_query_conditions = {
    dt: f"zanaverse_onboarding.permissions.pqc_{dt.lower().replace(' ', '_')}"
    for dt, cfg in (_pol.get("pqc_doctypes") or {}).items()
    if cfg and cfg.get("enabled") and hasattr(perm, f"pqc_{dt.lower().replace(' ', '_')}")
}

has_permission = {
    "Employee": "zanaverse_onboarding.permissions.has_permission_employee",
}

# --- Install / Migrate hooks ---
after_install = "zanaverse_onboarding.install.after_install"
after_migrate = "zanaverse_onboarding.install.after_migrate"

# Ensure required Module/Doctype exist before migrations
before_migrate = ["zanaverse_onboarding.patches.ensure_module_and_doctype.execute"]
