# Letterhead helpers for multi-company + brand setups.
# Scans blueprint assets and ensures matching Letter Head docs exist
# with the correct image attached (idempotent, safe to re-run).

from typing import Optional
import os
import glob

import frappe
from frappe.utils.file_manager import save_file


def _has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).get_field(fieldname))
    except Exception:
        return False


def _cleanup_old_files(doctype: str, docname: str) -> None:
    """Delete ALL existing file attachments for this doc so the new image
    becomes the only attachment (prevents hitting the max-attachments limit)."""
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
            "is_folder": 0,
        },
        pluck="name",
    )
    for fn in files:
        try:
            frappe.delete_doc("File", fn, ignore_permissions=True, force=True)
        except Exception:
            # if one row is already gone, don't break the whole run
            frappe.db.rollback()


def _ensure_letterhead_record(
    name: str,
    image_path: str,
    *,
    company: Optional[str] = None,
    brand: Optional[str] = None,
    is_default: int = 0,
) -> None:
    """Create/update a Letter Head with the given image. Idempotent."""
    doctype = "Letter Head"

    # fetch or create the doc
    if frappe.db.exists(doctype, name):
        lh = frappe.get_doc(doctype, name)
    else:
        payload = {"doctype": doctype, "letter_head_name": name}
        if company and _has_field(doctype, "company"):
            payload["company"] = company
        lh = frappe.get_doc(payload)
        lh.insert(ignore_permissions=True)

    # ensure we won't accumulate attachments over time
    _cleanup_old_files(doctype, lh.name)

    # attach the image and configure the doc to use it
    with open(image_path, "rb") as f:
        filedoc = save_file(
            os.path.basename(image_path),
            f.read(),
            doctype,
            lh.name,
            is_private=0,
        )

    lh.source = "Image"
    lh.image = filedoc.file_url

    if company and _has_field(doctype, "company"):
        lh.company = company
    if brand and _has_field(doctype, "brand"):
        lh.brand = brand
    if _has_field(doctype, "is_default"):
        lh.is_default = 1 if is_default else 0

    lh.save(ignore_permissions=True)


def ensure_letterheads(docs, assets_dir: str) -> None:
    """
    Scan:
      - {assets_dir}/letterheads/company/<Company>[-default].(png|jpg|jpeg|svg|webp|gif)
      - {assets_dir}/letterheads/brand/<Brand>.(png|jpg|jpeg|svg|webp|gif)

    For each file found:
      • company: create/update "<Company> Letter Head"
                 if filename ends with "-default", mark as default when the field exists.
                 (Skip if Company doesn't exist yet to keep runs safe & order-agnostic.)
      • brand:   create/update "<Brand> Brand Letter Head"
                 (shared, no default flag)
    """
    base = os.path.join(assets_dir, "letterheads")
    exts = ("*.png", "*.jpg", "*.jpeg", "*.svg", "*.webp", "*.gif")

    # per-company letterheads
    comp_dir = os.path.join(base, "company")
    for pat in exts:
        for path in glob.glob(os.path.join(comp_dir, pat)):
            stem = os.path.splitext(os.path.basename(path))[0]

            is_default = False
            lower = stem.lower()
            if lower.endswith("-default"):
                stem = stem[: -len("-default")]
                is_default = True

            company_name = stem
            # company might be created in the same provision run; skip until it exists
            if not frappe.db.exists("Company", company_name):
                continue

            lh_name = f"{company_name} Letter Head"
            _ensure_letterhead_record(
                lh_name,
                path,
                company=company_name,
                brand=None,
                is_default=1 if is_default else 0,
            )

    # per-brand letterheads (shared)
    brand_dir = os.path.join(base, "brand")
    for pat in exts:
        for path in glob.glob(os.path.join(brand_dir, pat)):
            brand_name = os.path.splitext(os.path.basename(path))[0]
            lh_name = f"{brand_name} Brand Letter Head"
            _ensure_letterhead_record(
                lh_name,
                path,
                company=None,
                brand=brand_name,
                is_default=0,
            )
