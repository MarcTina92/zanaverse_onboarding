"""
ZanaSchools staging - "ZanaSchools Fee Invoice" print format for Sales Invoice,
set as the default (the Education portal's Download Invoice uses the default).
Renders a test PDF for a paid, a part-paid and an overdue invoice. Safe to re-run.
"""
import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

NAME = "ZanaSchools Fee Invoice"
HTML = r"""
{%- set fs = frappe.db.get_value("Fee Schedule", doc.fee_schedule, ["academic_year", "academic_term"], as_dict=True) if doc.fee_schedule else None -%}
{%- set pe = frappe.db.get_value("Program Enrollment", {"student": doc.student, "academic_year": fs.academic_year if fs else "", "docstatus": 1}, ["program", "student_batch_name"], as_dict=True) if doc.student else None -%}
{%- set guardians = frappe.get_all("Student Guardian", filters={"parent": doc.student, "parenttype": "Student"}, fields=["guardian_name", "relation"], order_by="idx") if doc.student else [] -%}
{%- set paid = (doc.grand_total or 0) - (doc.outstanding_amount or 0) -%}
{%- set overdue = doc.outstanding_amount > 0 and doc.due_date and frappe.utils.getdate(doc.due_date) < frappe.utils.getdate() -%}
{%- if doc.outstanding_amount <= 0 -%}{%- set stamp, colour = "PAID", "#1F7A4D" -%}
{%- elif overdue -%}{%- set stamp, colour = "OVERDUE", "#B42318" -%}
{%- elif paid > 0 -%}{%- set stamp, colour = "PART-PAID", "#B7791F" -%}
{%- else -%}{%- set stamp, colour = "DUE", "#1F5D4C" -%}{%- endif -%}
<style>
  .zs { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 10.5px; color: #1d2b27; }
  .zs h1 { font-size: 22px; letter-spacing: 3px; color: #1F5D4C; margin: 4px 0 0 0; }
  .zs .muted { color: #6b7a75; }
  .zs .lbl { font-size: 8.5px; text-transform: uppercase; letter-spacing: 1px; color: #6b7a75; }
  .zs .stamp { border: 2px solid {{ colour }}; color: {{ colour }}; font-weight: bold; letter-spacing: 2px;
               padding: 4px 12px; font-size: 13px; display: inline-block; }
  .zs table.grid { width: 100%; border-collapse: collapse; }
  .zs table.items th { background: #1F5D4C; color: #fff; text-align: left; padding: 7px 8px; font-size: 9.5px; letter-spacing: 1px; }
  .zs table.items td { padding: 7px 8px; border-bottom: 1px solid #e3e8e6; }
  .zs table.items tr:nth-child(even) td { background: #f6f8f7; }
  .zs .num { text-align: right; white-space: nowrap; }
  .zs table.sum td { padding: 5px 8px; }
  .zs .due td { background: #1F5D4C; color: #fff; font-weight: bold; font-size: 12px; }
  .zs .box { border: 1px solid #d9e1de; padding: 10px 12px; vertical-align: top; }
  .zs .gold { border-top: 3px solid #C9A23F; }
</style>
{% if letter_head and not no_letterhead %}<div style="margin-bottom:12px">{{ letter_head }}</div>{% endif %}
<div class="zs">
  <table class="grid"><tr>
    <td style="vertical-align:bottom">
      <h1>FEE INVOICE</h1>
      <div class="muted">No. {{ doc.name }}</div>
    </td>
    <td style="text-align:right;vertical-align:bottom"><span class="stamp">{{ stamp }}</span></td>
  </tr></table>

  <table class="grid" style="margin-top:14px"><tr>
    <td class="box" style="width:50%">
      <div class="lbl">Student</div>
      <div style="font-size:13px;font-weight:bold;margin:2px 0">{{ doc.customer_name }}</div>
      <div class="muted">Student ID: {{ doc.student }}</div>
      {% if pe %}<div class="muted">Class: {{ pe.program }}{{ pe.student_batch_name or "" }}</div>{% endif %}
      {% if guardians %}<div style="margin-top:6px"><span class="lbl">Parent / Guardian</span><br>
        {% for g in guardians %}{{ g.guardian_name }} <span class="muted">({{ g.relation }})</span>{% if not loop.last %}<br>{% endif %}{% endfor %}</div>{% endif %}
    </td>
    <td style="width:2%"></td>
    <td class="box">
      <table class="grid">
        <tr><td class="lbl">Term</td><td class="num">{{ ((fs.academic_term if fs else "") or "-").split("(")[-1].rstrip(")") }}</td></tr>
        <tr><td class="lbl">Academic year</td><td class="num">{{ (fs.academic_year if fs else "") or "-" }}</td></tr>
        <tr><td class="lbl">Issue date</td><td class="num">{{ frappe.utils.formatdate(doc.posting_date, "d MMMM yyyy") }}</td></tr>
        <tr><td class="lbl">Payment due</td><td class="num" style="font-weight:bold">{{ frappe.utils.formatdate(doc.due_date, "d MMMM yyyy") }}</td></tr>
      </table>
    </td>
  </tr></table>

  <table class="grid items" style="margin-top:16px">
    <tr><th style="width:6%">#</th><th>Description</th><th class="num" style="width:22%">Amount</th></tr>
    {% for it in doc.items %}
    <tr><td>{{ loop.index }}</td>
        <td><b>{{ it.item_name }}</b>{% if it.description and it.description|striptags != it.item_name %}<br><span class="muted">{{ it.description|striptags }}</span>{% endif %}</td>
        <td class="num">{{ it.get_formatted("amount", doc) }}</td></tr>
    {% endfor %}
  </table>

  <table class="grid" style="margin-top:8px"><tr>
    <td style="width:52%"></td>
    <td><table class="grid sum">
      <tr><td>Total fees</td><td class="num">{{ doc.get_formatted("grand_total") }}</td></tr>
      <tr><td>Amount paid</td><td class="num">{{ frappe.utils.fmt_money(paid, currency=doc.currency) }}</td></tr>
      <tr class="due"><td>Balance due</td><td class="num">{{ doc.get_formatted("outstanding_amount") }}</td></tr>
    </table></td>
  </tr></table>

  {% if doc.outstanding_amount > 0 %}
  <table class="grid gold" style="margin-top:18px"><tr>
    <td style="padding-top:8px" colspan="3"><span class="lbl">How to pay</span> &nbsp;<span class="muted">Please quote <b>{{ doc.name }}</b> as the payment reference.</span></td></tr>
    <tr>
    <td class="box" style="width:32%"><b>Bank transfer</b><br>Zana Community Bank<br>Account: 0012 3456 78<br>Account name: Zana International School</td>
    <td class="box" style="width:32%"><b>Mobile money</b><br>Paybill: 400 500<br>Account: {{ doc.name }}<br><span class="muted">M-Pesa, MTN MoMo, Airtel Money</span></td>
    <td class="box"><b>Card or online</b><br>Pay securely from the Parent Portal<br><span class="muted">Visa, Mastercard, Paystack, Flutterwave</span></td>
  </tr></table>
  {% else %}
  <div style="margin-top:18px;padding:10px 12px;border:1px solid #cfe6da;background:#f1f8f4;color:#1F7A4D">
    Thank you &mdash; this invoice is fully paid.</div>
  {% endif %}

  <div class="muted" style="margin-top:16px;font-size:9px">
    Fees are payable by the due date shown. Please contact the Bursar's office on accounts@zis.demo with any questions about this invoice.
  </div>
</div>
"""

frappe.init(site="zanaschools-staging.zanaverse.com", sites_path="."); frappe.connect(); frappe.set_user("Administrator")
pf = frappe.get_doc("Print Format", NAME) if frappe.db.exists("Print Format", NAME) else frappe.new_doc("Print Format")
pf.update({"name": NAME, "doc_type": "Sales Invoice", "module": "Accounts", "standard": "No", "custom_format": 1,
           "print_format_type": "Jinja", "html": HTML, "disabled": 0, "margin_top": 15, "margin_bottom": 15})
if pf.is_new(): pf.flags.name_set = True; pf.insert(ignore_permissions=True)
else: pf.save(ignore_permissions=True)
make_property_setter("Sales Invoice", None, "default_print_format", NAME, "Data", for_doctype=True)
frappe.db.commit(); frappe.clear_cache()

print("print format :", NAME, "| default for Sales Invoice:",
      frappe.db.get_value("Property Setter", {"doc_type": "Sales Invoice", "property": "default_print_format"}, "value"))
from education.education import api
print("portal will use:", api.get_fees_print_format())
for label, filters in [("paid", {"status": "Paid"}), ("overdue", {"status": "Overdue"})]:
    si = frappe.db.get_value("Sales Invoice", dict(docstatus=1, fee_schedule=["is", "set"], **filters), "name")
    if not si: print(f"{label:8}: none found"); continue
    try:
        pdf = frappe.get_print("Sales Invoice", si, print_format=NAME, as_pdf=True)
        print(f"{label:8}: {si} -> PDF OK ({len(pdf):,} bytes)")
    except Exception as e:
        print(f"{label:8}: {si} -> FAILED: {str(e).splitlines()[-1][:200]}")
frappe.destroy()
