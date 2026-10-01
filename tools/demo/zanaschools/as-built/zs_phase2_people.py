"""
ZanaSchools demo - Phase 2: academic structure + people.
Dry run by default. ZS_APPLY=1 to write. Safe to re-run: all data is generated
deterministically up front, and anything that already exists is skipped.
"""
import os, re, random, datetime as dt
import frappe
from frappe.utils.password import update_password

SITE = "zanaschools-demo.zanaverse.com"
SITES = "/home/frappe/frappe-bench/sites"
APPLY = os.environ.get("ZS_APPLY") == "1"
COMPANY = "Zana International School"
DOMAIN = "zis.demo"
DEMO_PASSWORD = os.environ.get("ZS_DEMO_PASSWORD", "ZanaDemo#2026")
AY_PREV, AY_CUR, AY_NEXT = "2025-2026", "2026-2027", "2027-2028"
TERM1 = {AY_PREV: "2025-2026 (Term 1)", AY_CUR: "2026-2027 (Term 1)"}
START = {AY_PREV: dt.date(2025, 9, 1), AY_CUR: dt.date(2026, 9, 7)}
DRC = "Congo, The Democratic Republic of the"
rng = random.Random(2026)

# ------------------------------------------------------------------ curriculum
PRIMARY = ["English", "Mathematics", "Science", "Humanities", "French", "ICT",
           "Art & Design", "Physical Education", "Music"]
KS3 = ["English", "Mathematics", "Biology", "Chemistry", "Physics", "Geography", "History",
       "African Studies", "French", "Computer Science", "Art & Design", "Physical Education"]
IGCSE = ["English Language", "English Literature", "Mathematics", "Biology", "Chemistry",
         "Physics", "Economics", "Business Studies", "Geography", "History",
         "Computer Science", "French"]
ALEVEL = ["Mathematics", "Further Mathematics", "Biology", "Chemistry", "Physics", "Economics",
          "Business Studies", "Computer Science", "History", "English Literature"]
# program: (courses, arms, students per arm)
PROGRAMS = {
    "Year 4": (PRIMARY, ["A"], 14), "Year 5": (PRIMARY, ["A"], 14), "Year 6": (PRIMARY, ["A"], 14),
    "Year 7": (KS3, ["A", "B"], 16), "Year 8": (KS3, ["A"], 18), "Year 9": (KS3, ["A"], 18),
    "Year 10": (IGCSE, ["A", "B"], 14), "Year 11": (IGCSE, ["A"], 16),
    "Year 12": (ALEVEL, ["A"], 12), "Year 13": (ALEVEL, ["A"], 12),
}
ALL_COURSES = sorted(set(PRIMARY + KS3 + IGCSE + ALEVEL))
CATEGORIES = [("Day Student", 70), ("Boarding Student", 18), ("Scholarship", 8), ("Staff Child", 4)]
HOUSES = ["Kilimanjaro", "Zambezi", "Kalahari", "Niger"]
ROOMS = ([f"Classroom {p.replace('Year ', '')}{a}" for p, (_, arms, _) in PROGRAMS.items() for a in arms]
         + ["Science Lab 1", "Science Lab 2", "ICT Suite", "Art Studio", "Music Room",
            "Sports Hall", "Library", "Exam Hall"])

# ------------------------------------------------------------------ name pools
NAT = {  # country: (weight, male, female, surnames)
    "Nigeria": (25, ["Chinedu", "Tunde", "Emeka", "Ibrahim", "Olumide", "Ifeanyi", "Segun", "Musa", "Obinna", "Kelechi", "Tobi", "Femi"],
                ["Adaeze", "Funmilayo", "Ngozi", "Aisha", "Chiamaka", "Temitope", "Zainab", "Folake", "Nneka", "Amina", "Ifeoma", "Bisola"],
                ["Okafor", "Adeyemi", "Balogun", "Eze", "Nwosu", "Abubakar", "Okonkwo", "Ogunleye", "Bello", "Obi", "Uche", "Adeleke", "Danjuma"]),
    "Kenya": (18, ["Brian", "Kevin", "Kiprono", "Juma", "Baraka", "Collins", "Dennis", "Kamau"],
              ["Wanjiku", "Akinyi", "Faith", "Mercy", "Chebet", "Wambui", "Atieno", "Nyambura"],
              ["Otieno", "Kariuki", "Ochieng", "Kiplagat", "Njoroge", "Mutua", "Wafula", "Kimani"]),
    "Ghana": (12, ["Kwame", "Kofi", "Yaw", "Kwesi", "Nana", "Kojo"], ["Ama", "Abena", "Akosua", "Efua", "Adwoa", "Esi"],
              ["Mensah", "Owusu", "Boateng", "Appiah", "Ofori", "Darko", "Agyeman"]),
    "Zambia": (10, ["Mwila", "Chanda", "Bwalya", "Kabwe", "Chilufya"], ["Mutale", "Chileshe", "Mwape", "Thandiwe", "Namukolo"],
               ["Phiri", "Mwanza", "Tembo", "Zulu", "Lungu", "Musonda"]),
    "South Africa": (10, ["Sipho", "Thabo", "Lwazi", "Kagiso", "Themba"], ["Naledi", "Lerato", "Zanele", "Nomvula", "Palesa"],
                     ["Nkosi", "Mokoena", "Khumalo", "Ndlovu", "Molefe", "Mahlangu"]),
    DRC: (9, ["Ilunga", "Patrick", "Christian", "Junior", "Glody"], ["Esther", "Mbombo", "Nsimba", "Gloire", "Divine"],
          ["Kalala", "Mukendi", "Ngoy", "Kasongo", "Mbuyi", "Lukusa"]),
    "Uganda": (8, ["Isaac", "Moses", "Ronald", "Joel", "Brian"], ["Nakato", "Babirye", "Sarah", "Nabirye", "Prossy"],
               ["Okello", "Mugisha", "Nsubuga", "Ssempala", "Kato", "Tumusiime"]),
    "Senegal": (8, ["Mamadou", "Cheikh", "Ousmane", "Moussa", "Abdoulaye"], ["Fatou", "Aminata", "Awa", "Mariama", "Khady"],
                ["Diop", "Ndiaye", "Fall", "Sarr", "Diallo", "Faye"]),
}
PHONE = {"Nigeria": ("+234", ["803", "805", "806", "813", "816", "902"]), "Kenya": ("+254", ["712", "722", "733"]),
         "Ghana": ("+233", ["24", "54", "20"]), "Zambia": ("+260", ["97", "96"]), "South Africa": ("+27", ["82", "83", "72"]),
         DRC: ("+243", ["81", "82", "99"]), "Uganda": ("+256", ["77", "78"]), "Senegal": ("+221", ["77", "78"])}
OCCUPATIONS = ["Engineer", "Medical Doctor", "Banker", "Civil Servant", "Lawyer", "Entrepreneur", "Diplomat",
               "NGO Programme Manager", "Architect", "Pharmacist", "Accountant", "University Lecturer",
               "Energy Consultant", "IT Consultant", "Nurse", "Journalist"]
STREETS = ["Aguiyi Ironsi Street", "Mississippi Street", "Yakubu Gowon Crescent", "Gana Street", "Lobito Crescent",
           "Kumasi Crescent", "Nairobi Street", "Addis Ababa Crescent", "Lusaka Close", "Accra Street"]
AREAS = ["Maitama", "Wuse II", "Asokoro", "Jabi", "Gwarinpa", "Katampe", "Guzape"]
BLOOD = [("O+", 45), ("A+", 25), ("B+", 20), ("AB+", 4), ("O-", 3), ("A-", 2), ("B-", 1)]

# ------------------------------------------------------------------ staff
# (first, last, gender, designation, login_email or None, form group or None)
STAFF = [
    ("Adaeze", "Okonkwo", "Female", "Principal", f"principal@{DOMAIN}", None),
    ("Kwame", "Asante", "Male", "Deputy Principal", f"deputy@{DOMAIN}", None),
    ("Wanjiku", "Kamau", "Female", "Head of Primary", None, None),
    ("Thabo", "Molefe", "Male", "Bursar", f"bursar@{DOMAIN}", None),
    ("Fatou", "Ndiaye", "Female", "Registrar", f"registrar@{DOMAIN}", None),
    ("Esi", "Boateng", "Female", "Teacher", None, ("Year 4", "A")),
    ("Mutale", "Banda", "Female", "Teacher", None, ("Year 5", "A")),
    ("Olumide", "Adebayo", "Male", "Teacher", None, ("Year 6", "A")),
    ("Naledi", "Khumalo", "Female", "Head of Department", f"teacher@{DOMAIN}", ("Year 11", "A")),
    ("Baraka", "Otieno", "Male", "Teacher", None, ("Year 7", "A")),
    ("Ifeanyi", "Nwosu", "Male", "Head of Department", None, ("Year 10", "A")),
    ("Akinyi", "Ochieng", "Female", "Teacher", None, ("Year 8", "A")),
    ("Kojo", "Mensah", "Male", "Teacher", None, ("Year 9", "A")),
    ("Chanda", "Mulenga", "Male", "Teacher", None, ("Year 10", "B")),
    ("Nakato", "Nsubuga", "Female", "Teacher", None, ("Year 7", "B")),
    ("Ilunga", "Kasongo", "Male", "Head of Department", None, ("Year 12", "A")),
    ("Aminata", "Sow", "Female", "Teacher", None, None),
    ("Lwazi", "Dlamini", "Male", "Teacher", None, ("Year 13", "A")),
    ("Zainab", "Abubakar", "Female", "Teacher", None, None),
    ("Chileshe", "Phiri", "Female", "Teacher", None, None),
    ("Collins", "Wanjala", "Male", "Teacher", None, None),
]
TEACHING = {"Deputy Principal", "Head of Primary", "Teacher", "Head of Department"}
LOGIN_ROLES = {
    f"principal@{DOMAIN}": ["Education Manager", "Academics User", "Accounts User"],
    f"deputy@{DOMAIN}": ["Education Manager", "Academics User", "Instructor"],
    f"bursar@{DOMAIN}": ["Accounts User", "Accounts Manager", "Academics User"],
    f"registrar@{DOMAIN}": ["Education Manager", "Academics User"],
    f"teacher@{DOMAIN}": ["Instructor", "Academics User"],
}
OBSOLETE_BATCHES = ["Form 1", "Form 2", "Form 3", "Form 4"]
OBSOLETE_PROGRAMS = ["Secondary School"]
OLD_CUSTOMERS = ["David Mwangi", "Aisha Hassan", "Brian Otieno", "Grace Njeri", "Peter Banda",
                 "Mbav TSHILOMBO", "David Habacuc", "David  Habacuc"]

# ================================================================== generate plan (no DB)
def wchoice(pairs): return rng.choices([p[0] for p in pairs], [p[1] for p in pairs])[0]
def slug(s): return re.sub(r"[^a-z]", "", s.lower())
used_emails = set()
def email_for(first, last):
    base, n = f"{slug(first)}.{slug(last)}", 2
    e = f"{base}@{DOMAIN}"
    while e in used_emails:
        e = f"{base}{n}@{DOMAIN}"; n += 1
    used_emails.add(e); return e
def phone(country):
    if country != "Nigeria" and rng.random() < 0.5: country = "Nigeria"
    cc, pre = PHONE[country]
    return f"{cc} {rng.choice(pre)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"
def ynum(p): return int(p.split()[1])
def dob(n, start_year=2026):
    return dt.date(start_year - n - 5, 9, 1) + dt.timedelta(days=rng.randint(0, 364))

for s in STAFF:
    if s[4]: used_emails.add(s[4])

seats = [(p, a) for p, (_, arms, per) in PROGRAMS.items() for a in arms for _ in range(per)]
rng.shuffle(seats)
families = []
nat_w = [(k, v[0]) for k, v in NAT.items()]
while seats:
    k = rng.choices([1, 2, 3], [55, 33, 12])[0]
    fam_seats = [seats.pop(0)]
    for _ in range(k - 1):  # siblings sit in different year groups
        idx = next((j for j, st in enumerate(seats) if st[0] not in {x[0] for x in fam_seats}), None)
        if idx is None: break
        fam_seats.append(seats.pop(idx))
    country = wchoice(nat_w)
    _, males, females, surnames = NAT[country]
    surname = rng.choice(surnames)
    fam = {"surname": surname, "country": country, "category": wchoice(CATEGORIES),
           "house": rng.choice(HOUSES),
           "address": f"{rng.randint(2, 48)} {rng.choice(STREETS)}, {rng.choice(AREAS)}",
           "guardians": [], "kids": []}
    shape = rng.choices(["both", "mother", "father"], [82, 13, 5])[0]
    if shape in ("both", "father"):
        fn = rng.choice(males)
        fam["guardians"].append({"first": fn, "relation": "Father", "email": email_for(fn, surname),
                                 "phone": phone(country), "occupation": rng.choice(OCCUPATIONS)})
    if shape in ("both", "mother"):
        fn = rng.choice(females)
        fam["guardians"].append({"first": fn, "relation": "Mother", "email": email_for(fn, surname),
                                 "phone": phone(country), "occupation": rng.choice(OCCUPATIONS)})
    taken = set()
    for (prog, arm) in fam_seats:
        gender = rng.choice(["Male", "Female"])
        pool = [n for n in (males if gender == "Male" else females) if n not in taken] or (males + females)
        first = rng.choice(pool); taken.add(first)
        n = ynum(prog)
        new = rng.random() < (0.35 if prog in ("Year 7", "Year 12") else 0.15)
        birth = dob(n)
        if new:
            joined = START[AY_CUR]
        else:
            joined = dt.date(rng.randint(max(2018, birth.year + 4), 2025), 9, 1)
        if prog in ("Year 12", "Year 13"):
            subs = rng.sample([c for c in ALEVEL if c != "Further Mathematics"], 3)
            if "Mathematics" in subs and rng.random() < 0.4:
                subs.append("Further Mathematics")
            elif rng.random() < 0.5:
                subs.append(rng.choice([c for c in ALEVEL if c not in subs and c != "Further Mathematics"]))
            courses = sorted(subs)
        else:
            courses = PROGRAMS[prog][0]
        enr = [(AY_CUR, prog, arm, courses)]
        prev = f"Year {n - 1}"
        if not new and prev in PROGRAMS:
            prev_courses = courses if prev in ("Year 12",) else PROGRAMS[prev][0]
            enr.insert(0, (AY_PREV, prev, "A", prev_courses))
        fam["kids"].append({
            "first": first, "gender": gender, "dob": birth, "joined": joined,
            "email": email_for(first, surname), "blood": wchoice(BLOOD),
            "mobile": phone(country) if n >= 10 else None, "enrolments": enr})
    families.append(fam)

students = [(f, k) for f in families for k in f["kids"]]
applicants = []
for j in range(22):
    country = wchoice(nat_w)
    _, males, females, surnames = NAT[country]
    gender = rng.choice(["Male", "Female"]); first = rng.choice(males if gender == "Male" else females)
    last = rng.choice(surnames)
    if j < 18:
        ay, prog = AY_NEXT, rng.choice(["Year 4", "Year 4", "Year 7", "Year 7", "Year 7", "Year 10", "Year 12", "Year 12"])
        birth = dob(ynum(prog), 2027); status = rng.choices(["Applied", "Approved", "Rejected"], [9, 6, 3])[0]
        app_date = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randint(0, 27))
    else:
        ay, prog = AY_CUR, rng.choice(["Year 5", "Year 8", "Year 9"])
        birth = dob(ynum(prog)); status = "Applied"
        app_date = dt.date(2026, 9, 14) + dt.timedelta(days=rng.randint(0, 14))
    applicants.append({"first": first, "last": last, "gender": gender, "country": country, "program": prog,
                       "ay": ay, "dob": birth, "status": status, "date": app_date,
                       "email": email_for(first, last)})

# ================================================================== DB helpers
errors, created = [], {}
_meta = {}
def has(doctype, field):
    if doctype not in _meta: _meta[doctype] = frappe.get_meta(doctype)
    return _meta[doctype].has_field(field)
def clean(d):
    return {k: v for k, v in d.items() if k == "doctype" or has(d["doctype"], k)}
def attempt(label, fn):
    try:
        r = fn(); frappe.db.commit(); return r
    except Exception as e:
        frappe.db.rollback(); errors.append(f"{label}: {repr(e)[:240]}")
        frappe.local.message_log = []
        return None
def ins(d, submit=False):
    doc = frappe.get_doc(clean(d)); doc.flags.ignore_permissions = True
    doc.insert()
    if submit: doc.submit()
    created[d["doctype"]] = created.get(d["doctype"], 0) + 1
    return doc
def ensure(doctype, name_field, value, extra=None):
    if frappe.db.exists(doctype, {name_field: value}) or not APPLY: return
    attempt(f"{doctype} {value}", lambda: ins({"doctype": doctype, name_field: value, **(extra or {})}))
def delete(doctype, name):
    attempt(f"delete {doctype} {name}", lambda: frappe.delete_doc(doctype, name, force=1,
            ignore_permissions=True, delete_permanently=True))

# ================================================================== run
os.chdir(SITES)
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()
frappe.set_user("Administrator")
print(f"MODE: {'APPLY' if APPLY else 'DRY RUN (nothing written)'}\n")

print("== PLAN ==")
print(f"  programs {len(PROGRAMS)} | courses {len(ALL_COURSES)} | rooms {len(ROOMS)} | houses {len(HOUSES)}")
print(f"  staff {len(STAFF)} (instructors {sum(1 for s in STAFF if s[3] in TEACHING)}, logins {sum(1 for s in STAFF if s[4])})")
print(f"  families {len(families)} | guardians {sum(len(f['guardians']) for f in families)} | students {len(students)}")
print(f"  families with siblings: {sum(1 for f in families if len(f['kids']) > 1)}")
by_cls = {}
for f, k in students:
    _, p, a, _ = k["enrolments"][-1]; by_cls[f"{p}{a}"] = by_cls.get(f"{p}{a}", 0) + 1
print("  class sizes:", by_cls)
print(f"  program enrolments: {sum(len(k['enrolments']) for _, k in students)} "
      f"({sum(1 for _, k in students if len(k['enrolments']) == 2)} with 2025-26 history)")
print(f"  applicants {len(applicants)}")
nat_count = {}
for f, k in students: nat_count[f["country"]] = nat_count.get(f["country"], 0) + 1
print("  nationalities:", nat_count)
print("  sample:", [(f"{k['first']} {f['surname']}", k["enrolments"][-1][1] + k["enrolments"][-1][2], f["country"])
                    for f, k in students[:5]])

print("\n== LINK TARGET CHECKS ==")
for g in ("Male", "Female"): print(f"  Gender {g}: {bool(frappe.db.exists('Gender', g))}")
for c in NAT: print(f"  Country {c}: {bool(frappe.db.exists('Country', c))}")
for r in sorted({r for rs in LOGIN_ROLES.values() for r in rs}):
    print(f"  Role {r}: {bool(frappe.db.exists('Role', r))}")
print("  Education Settings has user_creation_skip:", has("Education Settings", "user_creation_skip"))

if not APPLY:
    frappe.destroy(); print("\nDry run complete."); raise SystemExit

# ---- 0. obsolete masters
print("\n== 0. Remove obsolete masters ==")
for p in OBSOLETE_PROGRAMS:
    if frappe.db.exists("Program", p): delete("Program", p)
for b in OBSOLETE_BATCHES:
    if frappe.db.exists("Student Batch Name", b): delete("Student Batch Name", b)
for r in frappe.get_all("Room", fields=["name", "room_name"]):
    if r.room_name not in ROOMS: delete("Room", r.name)
staff_names = {f"{s[0]} {s[1]}" for s in STAFF}
for ins_row in frappe.get_all("Instructor", fields=["name", "instructor_name"]):
    if ins_row.instructor_name not in staff_names: delete("Instructor", ins_row.name)
for c in frappe.get_all("Customer", filters={"customer_name": ["in", OLD_CUSTOMERS]}, pluck="name"):
    delete("Customer", c)
if has("Education Settings", "user_creation_skip"):
    frappe.db.set_single_value("Education Settings", "user_creation_skip", 1); frappe.db.commit()

# ---- 1. masters
print("== 1. Masters ==")
if not frappe.db.exists("Academic Year", AY_NEXT):
    attempt("AY next", lambda: ins({"doctype": "Academic Year", "academic_year_name": AY_NEXT,
                                     "year_start_date": "2027-09-01", "year_end_date": "2028-08-31"}))
for c, _ in CATEGORIES: ensure("Student Category", "category", c)
for a in ("A", "B"): ensure("Student Batch Name", "batch_name", a)
for h in HOUSES: ensure("School House", "house_name", h)
for r in ROOMS:
    cap = 60 if r in ("Sports Hall", "Exam Hall") else (30 if r.startswith("Classroom") else 24)
    ensure("Room", "room_name", r, {"seating_capacity": cap})
for d in sorted({s[3] for s in STAFF}): ensure("Designation", "designation_name", d)
for c in ALL_COURSES: ensure("Course", "course_name", c)
for p, (courses, _, _) in PROGRAMS.items():
    if not frappe.db.exists("Program", p):
        req = 0 if p in ("Year 12", "Year 13") else 1
        attempt(f"Program {p}", lambda p=p, courses=courses, req=req: ins({
            "doctype": "Program", "program_name": p, "program_abbreviation": p.replace("Year ", "Y"),
            "courses": [{"course": c, "course_name": c, "required": req} for c in courses]}))

# ---- 2. staff
print("== 2. Staff ==")
instructor_of = {}
for first, last, gender, desig, login, form in STAFF:
    full = f"{first} {last}"
    if login and not frappe.db.exists("User", login):
        def mk_user(first=first, last=last, login=login):
            u = frappe.get_doc({"doctype": "User", "email": login, "first_name": first, "last_name": last,
                                "send_welcome_email": 0, "user_type": "System User",
                                "roles": [{"role": r} for r in LOGIN_ROLES[login] if frappe.db.exists("Role", r)]})
            u.flags.ignore_permissions = True; u.insert()
            update_password(login, DEMO_PASSWORD)
            created["User"] = created.get("User", 0) + 1
        attempt(f"User {login}", mk_user)
    emp = frappe.db.get_value("Employee", {"first_name": first, "last_name": last, "company": COMPANY})
    if not emp:
        d = {"doctype": "Employee", "first_name": first, "last_name": last, "gender": gender,
             "date_of_birth": dt.date(rng.randint(1970, 1994), rng.randint(1, 12), rng.randint(1, 28)),
             "date_of_joining": dt.date(rng.randint(2012, 2024), 8, 25), "company": COMPANY,
             "status": "Active", "designation": desig, "cell_number": phone("Nigeria"),
             "company_email": login or f"{slug(first)}.{slug(last)}@{DOMAIN}"}
        if login: d["user_id"] = login
        r = attempt(f"Employee {full}", lambda d=d: ins(d))
        emp = r.name if r else None
    if desig in TEACHING:
        ins_name = frappe.db.get_value("Instructor", {"instructor_name": full})
        if not ins_name:
            r = attempt(f"Instructor {full}", lambda full=full, gender=gender, emp=emp: ins({
                "doctype": "Instructor", "instructor_name": full, "gender": gender,
                "employee": emp, "status": "Active"}))
            ins_name = r.name if r else None
        if form and ins_name: instructor_of[form] = (ins_name, full)

# ---- 3/4. guardians + students
print("== 3. Guardians & students ==")
student_of = {}
for f in families:
    g_rows = []
    for g in f["guardians"]:
        gname = frappe.db.get_value("Guardian", {"email_address": g["email"]})
        if not gname:
            r = attempt(f"Guardian {g['email']}", lambda g=g, f=f: ins({
                "doctype": "Guardian", "guardian_name": f"{g['first']} {f['surname']}",
                "email_address": g["email"], "mobile_number": g["phone"], "occupation": g["occupation"]}))
            gname = r.name if r else None
        if gname:
            g_rows.append({"guardian": gname, "guardian_name": f"{g['first']} {f['surname']}", "relation": g["relation"]})
    for k in f["kids"]:
        sname = frappe.db.get_value("Student", {"student_email_id": k["email"]})
        if not sname:
            d = {"doctype": "Student", "first_name": k["first"], "last_name": f["surname"],
                 "student_email_id": k["email"], "gender": k["gender"], "date_of_birth": k["dob"],
                 "blood_group": k["blood"], "joining_date": k["joined"], "nationality": f["country"],
                 "country": "Nigeria", "city": "Abuja", "address_line_1": f["address"],
                 "student_mobile_number": k["mobile"], "guardians": g_rows}
            r = attempt(f"Student {k['email']}", lambda d=d: ins(d))
            sname = r.name if r else None
        if sname: student_of[k["email"]] = sname
print("   siblings")
for f in families:
    if len(f["kids"]) < 2: continue
    for k in f["kids"]:
        me = student_of.get(k["email"])
        if not me or frappe.db.count("Student Sibling", {"parent": me}): continue
        def add_sibs(me=me, k=k, f=f):
            doc = frappe.get_doc("Student", me)
            for o in f["kids"]:
                if o is k or o["email"] not in student_of: continue
                doc.append("siblings", {"studying_in_same_institute": "YES", "student": student_of[o["email"]],
                                        "full_name": f"{o['first']} {f['surname']}", "gender": o["gender"],
                                        "date_of_birth": o["dob"]})
            doc.flags.ignore_permissions = True; doc.save()
        attempt(f"Siblings {me}", add_sibs)

# ---- 5. program enrolments
print("== 4. Program enrolments (this takes a few minutes) ==")
roster = {}  # (ay, prog, arm) -> [(student, name)]
alevel_roster = {}  # (prog, course) -> [(student, name)]
for f, k in students:
    sname = student_of.get(k["email"])
    if not sname: continue
    full = f"{k['first']} {f['surname']}"
    for ay, prog, arm, courses in k["enrolments"]:
        roster.setdefault((ay, prog, arm), []).append((sname, full))
        if ay == AY_CUR and prog in ("Year 12", "Year 13"):
            for c in courses: alevel_roster.setdefault((prog, c), []).append((sname, full))
        if frappe.db.exists("Program Enrollment", {"student": sname, "program": prog,
                                                    "academic_year": ay, "docstatus": 1}):
            continue
        attempt(f"PE {sname} {prog} {ay}", lambda sname=sname, prog=prog, ay=ay, arm=arm, courses=courses, f=f: ins({
            "doctype": "Program Enrollment", "student": sname, "program": prog, "academic_year": ay,
            "academic_term": TERM1[ay], "enrollment_date": START[ay], "student_batch_name": arm,
            "student_category": f["category"], "school_house": f["house"],
            "courses": [{"course": c, "course_name": c} for c in courses]}, submit=True))

# ---- 6. student groups
print("== 5. Student groups ==")
for (ay, prog, arm), members in sorted(roster.items()):
    gname = f"{prog}{arm} ({ay})"
    if frappe.db.exists("Student Group", gname): continue
    tutor = instructor_of.get((prog, arm))
    attempt(f"Group {gname}", lambda gname=gname, ay=ay, prog=prog, arm=arm, members=members, tutor=tutor: ins({
        "doctype": "Student Group", "student_group_name": gname, "group_based_on": "Batch",
        "academic_year": ay, "program": prog, "batch": arm,
        "students": [{"student": s, "student_name": n, "group_roll_number": i + 1, "active": 1}
                     for i, (s, n) in enumerate(sorted(members, key=lambda x: x[1]))],
        "instructors": [{"instructor": tutor[0], "instructor_name": tutor[1]}] if tutor else []}))
for (prog, course), members in sorted(alevel_roster.items()):
    gname = f"{prog} {course} ({AY_CUR})"
    if frappe.db.exists("Student Group", gname): continue
    attempt(f"Group {gname}", lambda gname=gname, prog=prog, course=course, members=members: ins({
        "doctype": "Student Group", "student_group_name": gname, "group_based_on": "Course",
        "academic_year": AY_CUR, "program": prog, "course": course,
        "students": [{"student": s, "student_name": n, "group_roll_number": i + 1, "active": 1}
                     for i, (s, n) in enumerate(sorted(members, key=lambda x: x[1]))]}))

# ---- 7. demo student logins (one Year 10, one Year 12)
print("== 6. Demo student logins ==")
demo_students = []
for want in ("Year 10", "Year 12"):
    for f, k in students:
        if k["enrolments"][-1][1] == want and k["email"] in student_of:
            demo_students.append((k, f)); break
for k, f in demo_students:
    if frappe.db.exists("User", k["email"]): continue
    def mk(k=k, f=f):
        u = frappe.get_doc({"doctype": "User", "email": k["email"], "first_name": k["first"],
                            "last_name": f["surname"], "send_welcome_email": 0, "user_type": "Website User",
                            "roles": [{"role": "Student"}]})
        u.flags.ignore_permissions = True; u.insert()
        update_password(k["email"], DEMO_PASSWORD)
        frappe.db.set_value("Student", student_of[k["email"]], "user", k["email"])
    attempt(f"Student login {k['email']}", mk)

# ---- 8. applicants
print("== 7. Admissions pipeline ==")
if not frappe.db.exists("Academic Term", "2027-2028 (Term 1)"): attempt("Term 2027-2028", lambda: ins({"doctype": "Academic Term", "academic_year": AY_NEXT, "term_name": "Term 1", "term_start_date": "2027-09-06", "term_end_date": "2027-12-10"}))
for a in applicants:
    if frappe.db.exists("Student Applicant", {"student_email_id": a["email"]}): continue
    attempt(f"Applicant {a['email']}", lambda a=a: ins({
        "doctype": "Student Applicant", "first_name": a["first"], "last_name": a["last"],
        "program": a["program"], "academic_year": a["ay"], "academic_term": {AY_NEXT: "2027-2028 (Term 1)", AY_CUR: "2026-2027 (Term 2)"}[a["ay"]], "application_status": a["status"],
        "application_date": a["date"], "student_email_id": a["email"], "gender": a["gender"],
        "date_of_birth": a["dob"], "nationality": a["country"], "country": "Nigeria", "city": "Abuja"}))

# ---- verify
print("\n== VERIFY ==")
for d in ["Program", "Course", "Room", "School House", "Student Category", "Instructor", "Employee",
          "Guardian", "Student", "Student Sibling", "Program Enrollment", "Course Enrollment",
          "Student Group", "Student Applicant"]:
    print(f"  {d}: {frappe.db.count(d)}")
print("  created this run:", created)
print("  staff logins:", [s[4] for s in STAFF if s[4]])
print("  student logins:", [k["email"] for k, _ in demo_students])
print(f"\nERRORS ({len(errors)}):" if errors else "\nNo errors.")
for x in errors[:40]: print("  ", x)
if len(errors) > 40: print(f"   ... and {len(errors) - 40} more")
frappe.destroy()
