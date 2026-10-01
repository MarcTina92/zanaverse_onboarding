"""
ZanaSchools staging - school branding (option C: school brand, "Powered by Zanaverse").
Adds the Zana International School crest + wide logo, letterhead, school contact details,
and switches product surfaces from Zanaverse to the school. Safe to re-run.
"""
import frappe
SITE = "zanaschools-staging.zanaverse.com"
SCHOOL = "Zana International School"
ADDRESS = "14 Unity Avenue, Harmony Heights, Zana City"
PHONE, EMAIL, WEB = "+000 400 5000", "accounts@zis.demo", "www.zanaschool.demo"
CREST = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">\n  <defs>\n    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">\n      <stop offset="0" stop-color="#1F5D4C"/><stop offset="1" stop-color="#143F34"/>\n    </linearGradient>\n  </defs>\n  <path d="M120 12 L212 42 V112 C212 170 172 208 120 228 C68 208 28 170 28 112 V42 Z" fill="url(#g)" stroke="#C9A23F" stroke-width="7"/>\n  <path d="M120 30 L196 55 V112 C196 160 163 192 120 210 C77 192 44 160 44 112 V55 Z" fill="none" stroke="#C9A23F" stroke-width="1.5" opacity="0.6"/>\n  <!-- baobab tree -->\n  <g fill="#C9A23F">\n    <path d="M110 132 C112 116 111 104 106 92 L134 92 C129 104 128 116 130 132 Z"/>\n    <path d="M108 96 C100 88 92 84 84 84 M132 96 C140 88 148 84 156 84 M114 94 C112 84 108 76 102 70 M126 94 C128 84 132 76 138 70 M120 92 V64" stroke="#C9A23F" stroke-width="5" stroke-linecap="round" fill="none"/>\n    <ellipse cx="84" cy="80" rx="15" ry="9"/><ellipse cx="156" cy="80" rx="15" ry="9"/>\n    <ellipse cx="102" cy="66" rx="14" ry="9"/><ellipse cx="138" cy="66" rx="14" ry="9"/>\n    <ellipse cx="120" cy="58" rx="16" ry="10"/>\n  </g>\n  <!-- open book -->\n  <path d="M60 150 C80 140 104 142 120 152 C136 142 160 140 180 150 V184 C160 176 136 178 120 188 C104 178 80 176 60 184 Z" fill="#F4EBD0"/>\n  <path d="M120 152 V188" stroke="#1F5D4C" stroke-width="3"/>\n  <path d="M72 158 C88 153 102 154 112 160 M72 168 C88 163 102 164 112 170 M128 160 C138 154 152 153 168 158 M128 170 C138 164 152 163 168 168" stroke="#1F5D4C" stroke-width="2" fill="none" opacity="0.55"/>\n  <!-- stars -->\n  <g fill="#C9A23F">\n    <circle cx="70" cy="118" r="4"/><circle cx="170" cy="118" r="4"/>\n  </g>\n</svg>'
WIDE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 240" width="900" height="240">\n  <g transform="translate(0,0)">\n    <path d="M120 12 L212 42 V112 C212 170 172 208 120 228 C68 208 28 170 28 112 V42 Z" fill="#1F5D4C" stroke="#C9A23F" stroke-width="7"/>\n    <g fill="#C9A23F">\n    <path d="M110 132 C112 116 111 104 106 92 L134 92 C129 104 128 116 130 132 Z"/>\n    <path d="M108 96 C100 88 92 84 84 84 M132 96 C140 88 148 84 156 84 M114 94 C112 84 108 76 102 70 M126 94 C128 84 132 76 138 70 M120 92 V64" stroke="#C9A23F" stroke-width="5" stroke-linecap="round" fill="none"/>\n    <ellipse cx="84" cy="80" rx="15" ry="9"/><ellipse cx="156" cy="80" rx="15" ry="9"/>\n    <ellipse cx="102" cy="66" rx="14" ry="9"/><ellipse cx="138" cy="66" rx="14" ry="9"/>\n    <ellipse cx="120" cy="58" rx="16" ry="10"/>\n  </g>\n    <path d="M60 150 C80 140 104 142 120 152 C136 142 160 140 180 150 V184 C160 176 136 178 120 188 C104 178 80 176 60 184 Z" fill="#F4EBD0"/>\n    <path d="M120 152 V188" stroke="#1F5D4C" stroke-width="3"/>\n    <g fill="#C9A23F"><circle cx="70" cy="118" r="4"/><circle cx="170" cy="118" r="4"/></g>\n  </g>\n  <text x="250" y="112" font-family="Georgia, \'DejaVu Serif\', serif" font-size="64" font-weight="700" fill="#1F5D4C" textLength="300" lengthAdjust="spacingAndGlyphs">ZANA</text>\n  <text x="252" y="160" font-family="Georgia, \'DejaVu Serif\', serif" font-size="30" fill="#1F5D4C" textLength="600" lengthAdjust="spacingAndGlyphs">INTERNATIONAL SCHOOL</text>\n  <line x1="252" y1="178" x2="852" y2="178" stroke="#C9A23F" stroke-width="3"/>\n  <text x="252" y="212" font-family="Georgia, \'DejaVu Serif\', serif" font-size="20" font-style="italic" fill="#8A6D1E" textLength="470" lengthAdjust="spacingAndGlyphs">Knowledge · Unity · Excellence</text>\n</svg>'

frappe.init(site=SITE, sites_path="."); frappe.connect(); frappe.set_user("Administrator")

def put_file(name, content):
    path = frappe.get_site_path("public", "files", name)
    with open(path, "w") as f: f.write(content)
    url = f"/files/{name}"
    if not frappe.db.exists("File", {"file_url": url}):
        frappe.get_doc({"doctype": "File", "file_name": name, "file_url": url, "is_private": 0}).insert(ignore_permissions=True)
    return url

crest_url = put_file("zis-crest.svg", CREST)
wide_url = put_file("zis-logo-wide.svg", WIDE)

# letterhead (table layout: wkhtmltopdf's engine does not do flexbox)
lh_html = f"""<table style="width:100%;border-bottom:3px solid #C9A23F;padding-bottom:6px"><tr>
<td style="vertical-align:middle"><img src="{wide_url}" style="height:68px"></td>
<td style="vertical-align:middle;text-align:right;font-size:10px;line-height:1.5;color:#1F5D4C">
{ADDRESS}<br>{PHONE} &middot; {EMAIL}<br>{WEB}</td></tr></table>"""
if frappe.db.exists("Letter Head", SCHOOL):
    lh = frappe.get_doc("Letter Head", SCHOOL)
else:
    lh = frappe.new_doc("Letter Head"); lh.letter_head_name = SCHOOL
lh.source = "HTML"; lh.content = lh_html; lh.is_default = 1
lh.footer_source = "HTML"
lh.footer = f"""<div style="text-align:center;font-size:8px;color:#8A8A8A">{SCHOOL} &middot; {ADDRESS} &middot; Powered by Zanaverse</div>"""
lh.save(ignore_permissions=True)

# school (tenant) identity
frappe.db.set_value("Company", SCHOOL, {"company_logo": crest_url, "email": EMAIL, "phone_no": PHONE,
                                         "website": WEB, "default_letter_head": SCHOOL})
frappe.db.set_single_value("Education Settings", "school_college_logo", crest_url)

# product surfaces -> school brand, discreet Zanaverse credit
ws = {"app_name": SCHOOL, "app_logo": crest_url, "favicon": crest_url, "splash_image": crest_url,
      "banner_image": wide_url, "footer_powered": "Powered by Zanaverse",
      "brand_html": f'<img src="{crest_url}" alt="{SCHOOL}" style="height:24px;vertical-align:middle"> {SCHOOL}'}
for k, v in ws.items(): frappe.db.set_single_value("Website Settings", k, v)
frappe.db.set_single_value("Navbar Settings", "app_logo", crest_url)
frappe.db.set_single_value("System Settings", "app_name", SCHOOL)
frappe.db.set_single_value("System Settings", "country", "Nigeria")
frappe.db.set_single_value("System Settings", "email_footer_address", f"{SCHOOL} &middot; Zana City &middot; Powered by Zanaverse")
frappe.db.commit()
frappe.clear_cache()

print("files      :", crest_url, wide_url)
print("letterhead :", lh.name, "(default)")
print("company    :", frappe.db.get_value("Company", SCHOOL, ["company_logo", "default_letter_head", "email"], as_dict=True))
print("website    :", {k: frappe.db.get_single_value("Website Settings", k) for k in ("app_name", "app_logo", "footer_powered")})
print("system     :", frappe.db.get_single_value("System Settings", "app_name"), "|", frappe.db.get_single_value("System Settings", "country"))
frappe.destroy()
