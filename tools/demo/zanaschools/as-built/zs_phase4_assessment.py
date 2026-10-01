"""
ZanaSchools demo - Phase 4: assessment and report cards.
Grading scales, assessment groups (year > term > CA1/CA2/Exam), assessment plans,
results for all of 2025-26 plus CA1 of the current term (CA2 and exams scheduled
ahead with no results). Dry run by default; ZS_APPLY=1 to write. Safe to re-run.
"""
import os, random, datetime as dt
from collections import defaultdict
import frappe
from frappe.utils import now_datetime, getdate

SITE = "zanaschools-demo.zanaverse.com"
SITES = "/home/frappe/frappe-bench/sites"
APPLY = os.environ.get("ZS_APPLY") == "1"
AY_PREV, AY_CUR = "2025-2026", "2026-2027"
ROOT = "All Assessment Groups"
TERMS = {
    AY_PREV: [("Term 1", dt.date(2025, 9, 1), dt.date(2025, 12, 5)),
              ("Term 2", dt.date(2026, 1, 12), dt.date(2026, 4, 10)),
              ("Term 3", dt.date(2026, 5, 4), dt.date(2026, 7, 24))],
    AY_CUR: [("Term 1", dt.date(2026, 9, 7), dt.date(2026, 12, 11))],
}
SCALES = {
    "ZIS Primary Descriptors": [("EX", 80, "Exceeding"), ("SE", 60, "Secure"),
                                ("DE", 40, "Developing"), ("EM", 0, "Emerging")],
    "ZIS Secondary (A*-U)": [("A*", 90, ""), ("A", 80, ""), ("B", 70, ""), ("C", 60, ""), ("D", 50, ""),
                             ("E", 40, ""), ("F", 30, ""), ("G", 20, ""), ("U", 0, "Ungraded")],
    "ZIS A-Level (A*-U)": [("A*", 90, ""), ("A", 80, ""), ("B", 70, ""), ("C", 60, ""), ("D", 50, ""),
                           ("E", 40, ""), ("U", 0, "Ungraded")],
}
# (component, criteria, max score, weeks from term start (negative = before term end), mean shift)
COMPONENTS = [("CA1", "Coursework", 20, 2, 2), ("CA2", "Class Test", 20, 7, 0), ("Exam", "Exam", 100, -2, -3)]
SLOT_TIMES = [("14:00:00", "14:45:00"), ("14:50:00", "15:35:00"), ("15:40:00", "16:25:00")]
COMMENTS = [(80, ["Excellent work, keep it up.", "Outstanding understanding shown.", "A superb result."]),
            (65, ["Good progress this term.", "Solid performance; aim higher next term.", "Consistent effort shown."]),
            (50, ["Satisfactory; needs to consolidate key topics.", "Some good work; revision should be more thorough."]),
            (0, ["Needs significant support in this subject.", "Please attend the after-school support sessions."])]
OLD_GROUPS = ["Term 2 Midterm", "Term 2 Exams"]   # leftovers from the old test data, child first

errors, created = [], defaultdict(int)
_meta = {}
def has(dtp, f):
    if dtp not in _meta: _meta[dtp] = frappe.get_meta(dtp)
    return _meta[dtp].has_field(f)
def attempt(label, fn):
    try:
        r = fn(); frappe.db.commit(); return r
    except Exception as e:
        frappe.db.rollback(); errors.append(f"{label}: {repr(e)[:240]}"); frappe.local.message_log = []
def ins(d, submit=False):
    doc = frappe.get_doc({k: v for k, v in d.items() if k == "doctype" or has(d["doctype"], k)})
    doc.flags.ignore_permissions = True; doc.insert()
    if submit: doc.submit()
    created[d["doctype"]] += 1; return doc
def ynum(p): return int(p.split()[1])
def scale_for(prog):
    n = ynum(prog)
    return "ZIS Primary Descriptors" if n <= 6 else ("ZIS A-Level (A*-U)" if n >= 12 else "ZIS Secondary (A*-U)")
def grade(scale, pct):
    for code, thr, _ in SCALES[scale]:
        if pct >= thr: return code
    return SCALES[scale][-1][0]
def comment_for(pct, seed):
    for thr, opts in COMMENTS:
        if pct >= thr: return random.Random(seed).choice(opts)
def weekdays_from(start, n):
    d, out = start, []
    while len(out) < n:
        if d.weekday() < 5: out.append(d)
        d += dt.timedelta(days=1)
    return out
def comp_start(ts, te, wk):
    d = ts + dt.timedelta(weeks=wk) if wk >= 0 else te + dt.timedelta(weeks=wk)
    while d.weekday() != 0: d += dt.timedelta(days=1)
    return d
def tg(ay, term): return f"{ay[2:4]}-{ay[7:9]} {term}"          # e.g. "25-26 Term 1"
def yg(ay): return f"{ay[:4]}-{ay[7:9]} Academic Year"            # e.g. "2025-26 Academic Year"

os.chdir(SITES)
frappe.init(site=SITE, sites_path=SITES)
frappe.connect()
frappe.set_user("Administrator")
TODAY = getdate()
print(f"MODE: {'APPLY' if APPLY else 'DRY RUN (nothing written)'} | today {TODAY}\n")

# ---------------------------------------------------------------- read structure
groups = frappe.get_all("Student Group", fields=["name", "academic_year", "program", "batch", "course",
                                                 "group_based_on"], limit_page_length=0)
members = defaultdict(list)
for m in frappe.get_all("Student Group Student", filters={"active": 1},
                        fields=["parent", "student", "student_name"], limit_page_length=0):
    members[m.parent].append((m.student, m.student_name))
pe_courses = defaultdict(set)
for r in frappe.db.sql("""select pe.student, pe.academic_year, pec.course from `tabProgram Enrollment` pe
        join `tabProgram Enrollment Course` pec on pec.parent = pe.name where pe.docstatus = 1""", as_dict=True):
    pe_courses[(r.student, r.academic_year)].add(r.course)
prog_courses = defaultdict(list)
for r in frappe.get_all("Program Course", fields=["parent", "course"], order_by="idx", limit_page_length=0):
    prog_courses[r.parent].append(r.course)

units = {AY_PREV: [], AY_CUR: []}
for g in groups:
    if g.academic_year not in units: continue
    if g.group_based_on == "Course":
        units[g.academic_year].append((g, g.course))
    elif g.group_based_on == "Batch":
        if g.academic_year == AY_CUR and ynum(g.program) >= 12: continue   # A-Level uses subject sets
        courses = prog_courses[g.program]
        if ynum(g.program) >= 12:
            taken = set()
            for s, _ in members[g.name]: taken |= pe_courses[(s, g.academic_year)]
            courses = [c for c in courses if c in taken]
        for c in courses: units[g.academic_year].append((g, c))

plans = []   # (ay, term, component index, group, course, date, slot)
for ay in (AY_PREV, AY_CUR):
    for term, ts, te in TERMS[ay]:
        for ci, (_, _, _, wk, _) in enumerate(COMPONENTS):
            days = weekdays_from(comp_start(ts, te, wk), 5)
            per_group = defaultdict(int)
            for g, c in units[ay]:
                k = per_group[g.name]; per_group[g.name] += 1
                plans.append((ay, term, ci, g, c, days[min(k // 3, 4)], k % 3))
def takes(g, s, c, ay): return g.group_based_on == "Course" or c in pe_courses[(s, ay)]
past = [p for p in plans if p[5] <= TODAY]
est = sum(1 for p in past for s, _ in members[p[3].name] if takes(p[3], s, p[4], p[0]))
print("== PLAN ==")
print(f"  (group, subject) units: 2025-26 {len(units[AY_PREV])}, current {len(units[AY_CUR])}")
print(f"  assessment plans {len(plans)} (with results {len(past)}, upcoming {len(plans) - len(past)})")
print(f"  results to generate ~{est}")
print("  existing assessment groups:", frappe.get_all("Assessment Group", pluck="name"))
print("  existing criteria:", frappe.get_all("Assessment Criteria", pluck="name"))
print("  root group present:", bool(frappe.db.exists("Assessment Group", ROOT)))

if not APPLY:
    frappe.destroy(); print("\nDry run complete."); raise SystemExit

# ---------------------------------------------------------------- 1. scales, criteria, groups
print("\n== 1. Scales, criteria, groups ==")
for gname in OLD_GROUPS:
    if frappe.db.exists("Assessment Group", gname) and not frappe.db.count("Assessment Plan", {"assessment_group": gname}):
        attempt(f"delete {gname}", lambda gname=gname: frappe.delete_doc("Assessment Group", gname,
                                                                          force=1, ignore_permissions=True))
for name, rows in SCALES.items():
    if not frappe.db.exists("Grading Scale", name):
        attempt(f"Scale {name}", lambda name=name, rows=rows: ins({
            "doctype": "Grading Scale", "grading_scale_name": name,
            "intervals": [{"grade_code": c, "threshold": t, "grade_description": d} for c, t, d in rows]},
            submit=True))
for _, crit, _, _, _ in COMPONENTS:
    if not frappe.db.exists("Assessment Criteria", crit):
        attempt(f"Criteria {crit}", lambda crit=crit: ins({"doctype": "Assessment Criteria",
                                                          "assessment_criteria": crit}))
def ensure_group(name, parent, is_group):
    if not frappe.db.exists("Assessment Group", name):
        attempt(f"AG {name}", lambda: ins({"doctype": "Assessment Group", "assessment_group_name": name,
                                           "parent_assessment_group": parent, "is_group": is_group}))
for ay in (AY_PREV, AY_CUR):
    ensure_group(yg(ay), ROOT, 1)
    for term, _, _ in TERMS[ay]:
        ensure_group(tg(ay, term), yg(ay), 1)
        for comp, *_ in COMPONENTS:
            ensure_group(f"{tg(ay, term)} {comp}", tg(ay, term), 0)

# ---------------------------------------------------------------- 2. plans
print("== 2. Assessment plans (a few minutes) ==")
plan_name = {}
existing = {(r.student_group, r.course, r.assessment_group): r.name for r in frappe.get_all(
    "Assessment Plan", filters={"docstatus": 1}, fields=["name", "student_group", "course", "assessment_group"],
    limit_page_length=0)}
for ay, term, ci, g, c, day, slot in plans:
    comp, crit, mx, _, _ = COMPONENTS[ci]
    ag = f"{tg(ay, term)} {comp}"
    key = (g.name, c, ag)
    if key in existing:
        plan_name[key] = existing[key]; continue
    doc = attempt(f"Plan {g.name} | {c} | {ag}", lambda: ins({
        "doctype": "Assessment Plan", "student_group": g.name, "assessment_group": ag,
        "grading_scale": scale_for(g.program), "program": g.program, "course": c, "academic_year": ay,
        "academic_term": f"{ay} ({term})", "schedule_date": day, "from_time": SLOT_TIMES[slot][0],
        "to_time": SLOT_TIMES[slot][1], "maximum_assessment_score": mx,
        "assessment_criteria": [{"assessment_criteria": crit, "maximum_score": mx}]}, submit=True))
    if doc: plan_name[key] = doc.name

# ---------------------------------------------------------------- 3. results (bulk)
print("== 3. Results (bulk) ==")
done = {(r.student, r.assessment_plan) for r in frappe.get_all(
    "Assessment Result", fields=["student", "assessment_plan"], limit_page_length=0)}
ability, aptitude, trend = {}, {}, {}
def pct_for(s, c, ay, t_idx, ci, shift):
    if s not in ability: ability[s] = random.Random(f"ab-{s}").gauss(0, 1)
    if (s, c) not in aptitude: aptitude[(s, c)] = random.Random(f"apt-{s}-{c}").gauss(0, 0.5)
    if (s, ay) not in trend: trend[(s, ay)] = random.Random(f"tr-{s}-{ay}").gauss(0, 0.2)
    noise = random.Random(f"n-{s}-{c}-{ay}-{t_idx}-{ci}").gauss(0, 0.35)
    z = ability[s] + aptitude[(s, c)] + trend[(s, ay)] * t_idx + noise
    return max(12.0, min(99.0, 63 + shift + 13 * z))

parents, children = [], []
for ay, term, ci, g, c, day, slot in plans:
    if day > TODAY: continue
    comp, crit, mx, _, shift = COMPONENTS[ci]
    ag = f"{tg(ay, term)} {comp}"
    pn = plan_name.get((g.name, c, ag))
    if not pn: continue
    scale = scale_for(g.program)
    t_idx = [t for t, _, _ in TERMS[ay]].index(term)
    for s, sn in members[g.name]:
        if not takes(g, s, c, ay) or (s, pn) in done: continue
        pct = pct_for(s, c, ay, t_idx, ci, shift)
        score = round(pct * mx / 100, 1); gr = grade(scale, pct)
        parents.append({"assessment_plan": pn, "program": g.program, "course": c, "academic_year": ay,
                        "academic_term": f"{ay} ({term})", "student": s, "student_name": sn,
                        "student_group": g.name, "assessment_group": ag, "grading_scale": scale,
                        "maximum_score": mx, "total_score": score, "grade": gr,
                        "comment": comment_for(pct, f"c-{s}-{pn}") if comp == "Exam" else None})
        children.append({"assessment_criteria": crit, "maximum_score": mx, "score": score, "grade": gr})
print(f"  inserting {len(parents)} results")

def bulk_results():
    if not parents: return
    prefix = f"EDU-RES-{getdate().year}-"
    cur = frappe.db.sql("select current from tabSeries where name=%s", prefix)
    start = cur[0][0] if cur else 0
    names = [f"{prefix}{str(start + i + 1).zfill(5)}" for i in range(len(parents))]
    frappe.db.sql("insert into tabSeries (name, current) values (%s, %s) on duplicate key update current=%s",
                  (prefix, start + len(parents), start + len(parents)))
    now, u = now_datetime(), "Administrator"
    pk = [k for k in parents[0] if has("Assessment Result", k)]
    frappe.db.bulk_insert("Assessment Result",
                          ["name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"] + pk,
                          [(n, u, now, now, u, 1, 0) + tuple(p[k] for k in pk) for n, p in zip(names, parents)])
    ck = [k for k in children[0] if has("Assessment Result Detail", k)]
    frappe.db.bulk_insert("Assessment Result Detail",
                          ["name", "parent", "parenttype", "parentfield", "owner", "creation", "modified",
                           "modified_by", "docstatus", "idx"] + ck,
                          [(frappe.generate_hash(length=12), n, "Assessment Result", "details", u, now, now, u, 1, 1)
                           + tuple(ch[k] for k in ck) for n, ch in zip(names, children)])
    created["Assessment Result"] += len(parents)
attempt("Results", bulk_results)

# ---------------------------------------------------------------- verify
print("\n== VERIFY ==")
for d in ["Grading Scale", "Assessment Criteria", "Assessment Group", "Assessment Plan",
          "Assessment Result", "Assessment Result Detail"]:
    print(f"  {d}: {frappe.db.count(d)}")
by = defaultdict(dict)
for r in frappe.db.sql("""select grading_scale, grade, count(*) n from `tabAssessment Result`
        where assessment_group like %s group by grading_scale, grade""", ("%Exam",), as_dict=True):
    by[r.grading_scale][r.grade] = r.n
for sc, d in by.items(): print(f"  exam grade spread {sc}: {dict(sorted(d.items()))}")
print("  created this run:", dict(created))
print(f"\nERRORS ({len(errors)}):" if errors else "\nNo errors.")
for x in errors[:30]: print("  ", x)
if len(errors) > 30: print(f"   ... and {len(errors) - 30} more")
frappe.destroy()
