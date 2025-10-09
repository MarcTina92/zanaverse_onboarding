import frappe
from .permissions import _load_policy

def _task_for_todo(doc):
    if doc.reference_type != "Task" or not doc.reference_name:
        return None
    try:
        return frappe.get_doc("Task", doc.reference_name)
    except Exception:
        return None

def _is_valid_user(user):
    if not user:
        return False
    return bool(frappe.db.exists("User", {"name": user, "enabled": 1}))

def on_todo_after_insert(doc, method=None):
    pol = _load_policy() or {}
    mode = ((pol.get("collab") or {}).get("on_task_assignment") or "none").lower()
    if mode not in {"share_write", "project_user"}:
        return

    if not _is_valid_user(getattr(doc, "allocated_to", None)):
        return

    task = _task_for_todo(doc)
    if not (task and getattr(task, "project", None)):
        return

    try:
        if mode == "share_write":
            name = frappe.db.get_value(
                "DocShare",
                {"share_doctype": "Project", "share_name": task.project, "user": doc.allocated_to},
            )
            if name:
                ds = frappe.get_doc("DocShare", name)
                if not (int(ds.read or 0) == 1 and int(ds.write or 0) == 1):
                    ds.read = 1
                    ds.write = 1
                    ds.save()
                    frappe.db.commit()
            else:
                frappe.get_doc({
                    "doctype": "DocShare",
                    "share_doctype": "Project",
                    "share_name": task.project,
                    "user": doc.allocated_to,
                    "read": 1,
                    "write": 1,
                }).insert(ignore_permissions=True)
                frappe.db.commit()

        elif mode == "project_user":
            exists = frappe.db.exists(
                "Project User",
                {"parent": task.project, "parenttype": "Project", "user": doc.allocated_to},
            )
            if not exists:
                proj = frappe.get_doc("Project", task.project)
                # Adjust child fields if your schema differs
                proj.append("users", {"user": doc.allocated_to, "permission": "Write"})
                proj.save()
                frappe.db.commit()

    except Exception:
        frappe.log_error(frappe.get_traceback(), "collab.on_todo_after_insert failed")

def on_todo_on_trash(doc, method=None):
    pol = _load_policy() or {}
    mode = ((pol.get("collab") or {}).get("on_task_assignment") or "none").lower()
    if mode not in {"share_write", "project_user"}:
        return

    assigned_user = getattr(doc, "allocated_to", None)
    if not _is_valid_user(assigned_user):
        return

    task = _task_for_todo(doc)
    # If task no longer exists, we can still try to downgrade/remove by inspecting doc.reference_name
    project = getattr(task, "project", None) if task else None
    if not project:
        return

    # only clean up if user has no other assignments in this project
    if _exists_other_assignment_on_same_project(assigned_user, project, exclude_todo_name=doc.name):
        return

    try:
        if mode == "share_write":
            # Optional: skip downgrading for privileged users
            if assigned_user not in {"Administrator", "System Manager"}:
                name = frappe.db.get_value(
                    "DocShare",
                    {"share_doctype": "Project", "share_name": project, "user": assigned_user},
                )
                if name:
                    ds = frappe.get_doc("DocShare", name)
                    if int(ds.write or 0) != 0:
                        ds.read = 1
                        ds.write = 0   # or delete the share if you prefer stricter cleanup
                        ds.save()
                        frappe.db.commit()

        elif mode == "project_user":
            # Keeping membership is safer; if you want hard cleanup, uncomment:
            # row = frappe.db.exists("Project User", {"parent": project, "parenttype":"Project", "user": assigned_user})
            # if row:
            #     frappe.delete_doc("Project User", row)
            #     frappe.db.commit()
            pass

    except Exception:
        frappe.log_error(frappe.get_traceback(), "collab.on_todo_on_trash failed")

def ensure_task_project_picker():
    """Per-site toggle (via policy) to let Task.project ignore User Permissions."""
    pol = _load_policy() or {}
    want = bool((pol.get("collab") or {}).get("ignore_user_permissions_on_task_project"))
    if not want:
        return
    try:
        exists = frappe.db.exists(
            "Property Setter",
            {"doc_type": "Task", "field_name": "project", "property": "ignore_user_permissions"},
        )
        if not exists:
            ps = frappe.get_doc({
                "doctype": "Property Setter",
                "doc_type": "Task",
                "field_name": "project",
                "doctype_or_field": "DocField",
                "property": "ignore_user_permissions",
                "property_type": "Check",
                "value": "1",
            })
            ps.insert(ignore_permissions=True)
            frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "collab.ensure_task_project_picker failed")

def ensure_project_financial_privacy():
    pol = _load_policy() or {}
    cfg = (pol.get("project_field_privacy") or {})
    if not cfg or not cfg.get("enabled"):
        return

    permlevel = int(cfg.get("permlevel", 1))
    fields = list(cfg.get("fields") or [])
    roles  = list(cfg.get("level1_roles") or [])
    strict = bool(cfg.get("strict_sync"))
    create_if_missing = bool(cfg.get("create_if_missing", True))

    if not fields or not roles:
        return

    meta = frappe.get_meta("Project")
    # 1) bump fields to permlevel via Property Setters
    for field in fields:
        if not meta.has_field(field):
            continue
        name = frappe.db.exists("Property Setter", {
            "doc_type": "Project", "field_name": field, "property": "permlevel"
        })
        if name:
            doc = frappe.get_doc("Property Setter", name)
            if str(doc.value) != str(permlevel):
                doc.value = str(permlevel); doc.save()
        else:
            frappe.get_doc({
                "doctype": "Property Setter",
                "doc_type": "Project",
                "field_name": field,
                "doctype_or_field": "DocField",
                "property": "permlevel",
                "property_type": "Int",
                "value": str(permlevel),
                "doctype_or_field": "DocField",
            }).insert(ignore_permissions=True)
    frappe.db.commit()

    # 2) ensure Custom DocPerm(read=1) at that permlevel for the roles
    for role in roles:
        row = frappe.get_all("Custom DocPerm",
            filters={"parent":"Project","permlevel":permlevel,"role":role},
            fields=["name","read"])
        if row:
            d = frappe.get_doc("Custom DocPerm", row[0]["name"])
            if int(d.read or 0) != 1:
                d.read = 1; d.save()
        elif create_if_missing:
            frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": "Project",
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": permlevel,
                "read": 1,
            }).insert(ignore_permissions=True)
    frappe.db.commit()

    if strict:
        others = frappe.get_all("Custom DocPerm",
            filters={"parent":"Project","permlevel":permlevel,"read":1},
            fields=["name","role"])
        for r in others:
            if r["role"] not in roles:
                d = frappe.get_doc("Custom DocPerm", r["name"])
                d.read = 0; d.save()
        frappe.db.commit()

def _exists_other_assignment_on_same_project(user, project, exclude_todo_name=None):
    """Returns True if the user still has another Task assignment in the same Project."""
    if not (user and project):
        return False
    params = [user, project]
    extra = ""
    if exclude_todo_name:
        extra = " AND td.name != %s"
        params.append(exclude_todo_name)

    return frappe.db.sql(
        f"""
        select 1
          from `tabToDo` td
          join `tabTask` t on t.name = td.reference_name
         where td.reference_type = 'Task'
           and td.allocated_to   = %s
           and t.project         = %s
           {extra}
         limit 1
        """,
        tuple(params),
        as_dict=False,
    ) != ()
