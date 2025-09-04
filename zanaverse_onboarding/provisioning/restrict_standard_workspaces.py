# zanaverse_onboarding/provisioning/restrict_standard_workspaces.py

import frappe

def restrict_standard_workspaces(
    dry_run: bool = True,
    include_modules: tuple[str, ...] | None = None,
    exclude_names: tuple[str, ...] = ("Zanaverse Home",),
    force: bool = True,
):
    """
    Make all (or selected) Workspaces non-public, except the ones in exclude_names.

    - public = 1  → visible to everyone
    - public = 0  → visible only to users with roles listed on the Workspace

    Parameters
    ----------
    dry_run : bool
        If True, only reports what would change. If False, writes to DB.
    include_modules : tuple[str, ...] | None
        If provided, only consider Workspaces whose `module` is in this list.
        Example: ("Accounts", "CRM")
    exclude_names : tuple[str, ...]
        Names of Workspaces to leave untouched (keep as-is, typically public).
    force : bool
        If True, flip anything that is currently public (except excluded).
        If False, only flip those that are public (no extra conditions).

    Returns
    -------
    dict
        Summary with examined/changed/skipped counts and lists of names.
    """
    exclude = set(exclude_names or ())

    # Build filters (optionally scope to modules)
    filters = {}
    if include_modules:
        filters["module"] = ["in", list(include_modules)]

    rows = frappe.get_all("Workspace", fields=["name", "public", "module"], filters=filters)

    changed, skipped = [], []

    for r in rows:
        nm = r["name"]
        if nm in exclude:
            skipped.append(nm)
            continue

        is_public = int(r.get("public") or 0) == 1

        # If it's public and we're allowed to flip it, do so
        if is_public:
            if dry_run:
                changed.append(nm)
            else:
                frappe.db.set_value("Workspace", nm, "public", 0)
                changed.append(nm)
        else:
            # already non-public
            skipped.append(nm)

    if not dry_run and changed:
        frappe.db.commit()

    return {
        "examined": len(rows),
        "changed": len(changed),
        "skipped": len(skipped),
        "changed_names": changed,
        "skipped_names": skipped,
    }

@frappe.whitelist()
def run_restrict_standard_workspaces(
    dry_run=1,
    include_modules=None,           # can be str or list from JSON
    exclude_names=None,             # can be str or list from JSON
    force=1,
):
    # normalize inputs coming from bench/HTTP
    def as_tuple(x):
        if x is None or x == "":
            return None
        if isinstance(x, (list, tuple)):
            return tuple(x)
        return (str(x),)

    return restrict_standard_workspaces(
        dry_run=bool(int(dry_run or 0)),
        include_modules=as_tuple(include_modules),
        exclude_names=as_tuple(exclude_names) or ("Zanaverse Home",),
        force=bool(int(force or 0)),
    )
