import os, frappe
def after_install():
    if os.environ.get("ZV_SKIP_AFTER_INSTALL") == "1":
        frappe.logger().info("Skipping after_install (ZV_SKIP_AFTER_INSTALL=1)")
        return
    # keep heavy provisioning out of hooks; put it in CLI
