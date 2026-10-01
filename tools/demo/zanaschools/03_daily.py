"""Demo pack 03: daily school life. Room names, weekly timetable (Course Schedules for Term 1 2026-27),
leave applications, attendance (2025-26 full year + current term to date), student logs, instructor teaching logs.
Needs 01 and 02. Dry run unless ZS_APPLY=1; safe to re-run."""
import os, random, datetime as dt
from collections import defaultdict
import frappe
from frappe.utils import now_datetime, getdate

from _common import SITE, APPLY, connect
AY_PREV, AY_CUR = "2025-2026", "2026-2027"
rng = random.Random(3033)

TERMS = {
    AY_PREV: [("2025-2026 (Term 1)", dt.date(2025, 9, 1), dt.date(2025, 12, 5)),
              ("2025-2026 (Term 2)", dt.date(2026, 1, 12), dt.date(2026, 4, 10)),
              ("2025-2026 (Term 3)", dt.date(2026, 5, 4), dt.date(2026, 7, 24))],
    AY_CUR: [("2026-2027 (Term 1)", dt.date(2026, 9, 7), dt.date(2026, 12, 11))],
}
HOLIDAYS = {
    "2025-10-01": "Independence Day", "2025-12-25": "Christmas Day", "2025-12-26": "Boxing Day",
    "2026-01-01": "New Year's Day", "2026-03-20": "Eid al-Fitr", "2026-04-03": "Good Friday",
    "2026-04-06": "Easter Monday", "2026-05-01": "Workers' Day", "2026-06-12": "Democracy Day",
    "2026-10-01": "Independence Day", "2026-12-25": "Christmas Day", "2026-12-28": "Boxing Day (observed)",
    "2027-01-01": "New Year's Day", "2027-03-10": "Eid al-Fitr", "2027-03-26": "Good Friday",
    "2027-03-29": "Easter Monday", "2027-05-17": "Eid al-Adha",
}
for s, e in [("2025-10-27", "2025-10-31"), ("2026-02-16", "2026-02-20"), ("2026-05-25", "2026-05-29"),
             ("2026-10-26", "2026-10-30"), ("2027-02-15", "2027-02-19"), ("2027-05-31", "2027-06-04")]:
    d = getdate(s)
    while d <= getdate(e):
        HOLIDAYS.setdefault(str(d), "Half Term"); d += dt.timedelta(days=1)

# ---------------------------------------------------------------- timetable rules
PERIODS = [("08:00:00", "08:45:00"), ("08:45:00", "09:30:00"), ("09:50:00", "10:35:00"),
           ("10:35:00", "11:20:00"), ("12:10:00", "12:55:00"), ("12:55:00", "13:40:00")]
SLOTS = [(d, p) for d in range(5) for p in range(len(PERIODS))]
ALLOC = {
    "primary": {"English": 6, "Mathematics": 6, "Science": 4, "Humanities": 3, "French": 2, "ICT": 2,
                "Art & Design": 2, "Physical Education": 3, "Music": 2},
    "ks3": {"English": 4, "Mathematics": 4, "Biology": 2, "Chemistry": 2, "Physics": 2, "Geography": 2,
            "History": 2, "African Studies": 2, "French": 3, "Computer Science": 2, "Art & Design": 2,
            "Physical Education": 3},
    "igcse": {"English Language": 3, "English Literature": 2, "Mathematics": 4, "Biology": 3, "Chemistry": 3,
              "Physics": 3, "Economics": 2, "Business Studies": 2, "Geography": 2, "History": 2,
              "Computer Science": 2, "French": 2},
}
CLASSES = [("Year 4", "A"), ("Year 5", "A"), ("Year 6", "A"), ("Year 7", "A"), ("Year 7", "B"),
           ("Year 8", "A"), ("Year 9", "A"), ("Year 10", "A"), ("Year 10", "B"), ("Year 11", "A")]
PRIMARY_TUTOR = {"Year 4": "Esi Boateng", "Year 5": "Mutale Banda", "Year 6": "Olumide Adebayo"}
TUTOR_SUBJECTS = {"English", "Mathematics", "Science", "ICT"}
TEACHERS = {
    "Humanities": ["Wanjiku Kamau"], "French": ["Aminata Sow"], "Physical Education": ["Collins Wanjala"],
    "Art & Design": ["Chileshe Phiri"], "Music": ["Chileshe Phiri"],
    "English": ["Baraka Otieno", "Naledi Khumalo"], "English Language": ["Naledi Khumalo", "Baraka Otieno"],
    "English Literature": ["Naledi Khumalo"], "Mathematics": ["Ifeanyi Nwosu", "Kwame Asante"],
    "Further Mathematics": ["Kwame Asante"], "Biology": ["Akinyi Ochieng"], "Chemistry": ["Kojo Mensah"],
    "Physics": ["Chanda Mulenga"], "Geography": ["Nakato Nsubuga"], "History": ["Ilunga Kasongo"],
    "African Studies": ["Ilunga Kasongo", "Nakato Nsubuga"], "Computer Science": ["Lwazi Dlamini"],
    "Economics": ["Zainab Abubakar"], "Business Studies": ["Zainab Abubakar"],
}
LABS = ["Science Lab 1", "Science Lab 2"]
SPECIAL_ROOMS = {"Biology": LABS, "Chemistry": LABS, "Physics": LABS, "Science": LABS,
                 "Computer Science": ["ICT Suite"], "ICT": ["ICT Suite"], "Art & Design": ["Art Studio"],
                 "Music": ["Music Room"], "Physical Education": ["Sports Hall"]}
SEMINAR = ["Classroom 12A", "Classroom 13A", "Library", "Exam Hall"]
COLORS = ["blue", "green", "red", "orange", "yellow", "teal", "violet", "cyan", "amber", "pink", "purple"]

LOGS = {
    "Achievement": ["Represented the school in the inter-schools debate competition in Abuja and reached the semi-final.",
                    "Awarded Star of the Week for outstanding effort in {subj}.",
                    "Selected for the school football team for the regional tournament.",
                    "Achieved the top score in the {subj} class test.",
                    "Led a house assembly on Africa Day, excellent public speaking.",
                    "Gold medal in the 200m at the inter-house sports day.",
                    "Completed the Duke of Edinburgh bronze expedition."],
    "Academic": ["Homework in {subj} consistently incomplete. Parents informed; review in two weeks.",
                 "Moved to the extension group in {subj} following strong assessment results.",
                 "Missed the {subj} coursework deadline; extension granted to Friday.",
                 "Additional reading support recommended; referred to learning support.",
                 "Excellent progress in {subj} this half term. Well done."],
    "General": ["Late to registration three times this week. Reminder given.",
                "Uniform reminder issued (blazer missing).",
                "Excellent contribution as class prefect; very helpful with new students.",
                "Mobile phone confiscated during lessons, returned to parent at pick-up.",
                "Volunteered at the school community clean-up day."],
    "Medical": ["Sent to the sick bay with a headache; parent collected at 12:30.",
                "Inhaler stored with the school nurse; care plan on file.",
                "Minor sports injury during PE, ice applied and parent informed.",
                "Returned to school after malaria treatment; doctor's note received."],
}
LEAVE_REASONS = [("Malaria, doctor's note provided.", 0), ("Family wedding abroad.", 0),
                 ("Representing the school at the regional athletics championships.", 1),
                 ("Religious observance.", 0), ("Hospital appointment.", 0),
                 ("Representing the school at the national maths olympiad.", 1), ("Bereavement in the family.", 0)]

# ---------------------------------------------------------------- helpers
errors, created = [], defaultdict(int)
_meta = {}
def has(doctype, f):
    if doctype not in _meta: _meta[doctype] = frappe.get_meta(doctype)
    return _meta[doctype].has_field(f)
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
def school_days(start, end):
    d, out = start, []
    while d <= end:
        if d.weekday() < 5 and str(d) not in HOLIDAYS: out.append(d)
        d += dt.timedelta(days=1)
    return out
def reserve_names(prefix, n):
    cur = frappe.db.sql("select current from tabSeries where name=%s", prefix)
    start = cur[0][0] if cur else 0
    if APPLY:
        frappe.db.sql("insert into tabSeries (name, current) values (%s, %s) "
                      "on duplicate key update current=%s", (prefix, start + n, start + n))
    return [f"{prefix}{str(start + i + 1).zfill(5)}" for i in range(n)]
def bulk(doctype, rows, series):
    if not rows: return
    names = reserve_names(series.replace(".YYYY.", str(getdate().year)).rstrip("#").rstrip("."), len(rows))
    now, user = now_datetime(), "Administrator"
    keys = [k for k in rows[0] if has(doctype, k)]
    fields = ["name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "naming_series"] + keys
    values = [(nm, user, now, now, user, r.pop("_docstatus", 0), 0, series) + tuple(r[k] for k in keys)
              for nm, r in zip(names, rows)]
    frappe.db.bulk_insert(doctype, fields, values)
    frappe.db.commit(); created[doctype] += len(rows)

# ---------------------------------------------------------------- connect
COMPANY = connect()
TODAY = getdate()
if APPLY:   # rooms are numbered by a series; give them their real names (timetable + portal show room names)
    for r in frappe.get_all("Room", fields=["name", "room_name"]):
        if r.name != r.room_name and not frappe.db.exists("Room", r.room_name):
            frappe.rename_doc("Room", r.name, r.room_name, force=True); frappe.db.commit()

ins_id = {r.instructor_name: r.name for r in frappe.get_all("Instructor", fields=["name", "instructor_name"])}
room_id = {r.room_name: r.name for r in frappe.get_all("Room", fields=["name", "room_name"])}
groups = {g.name: g for g in frappe.get_all("Student Group", fields=["name", "academic_year", "program", "batch",
                                                                         "course", "group_based_on"])}
members = defaultdict(list)
for m in frappe.get_all("Student Group Student", filters={"active": 1},
                        fields=["parent", "student", "student_name"], limit_page_length=0):
    members[m.parent].append((m.student, m.student_name))
batch_groups = {ay: [g for g in groups.values() if g.group_based_on == "Batch" and g.academic_year == ay]
                for ay in (AY_PREV, AY_CUR)}
missing = sorted(({t for ts in TEACHERS.values() for t in ts} | set(PRIMARY_TUTOR.values())) - set(ins_id))
print("== CHECKS ==")
print(f"  instructors found {len(ins_id)} | missing: {missing or 'none'}")
print(f"  rooms found {len(room_id)} | batch groups prev {len(batch_groups[AY_PREV])}, cur {len(batch_groups[AY_CUR])}")
print(f"  attendance_based_on_course_schedule currently:",
      frappe.db.get_single_value("Education Settings", "attendance_based_on_course_schedule"))

# ---------------------------------------------------------------- timetable template
units = []
for prog, arm in CLASSES:
    n = ynum(prog); stage = "primary" if n <= 6 else "ks3" if n <= 9 else "igcse"
    g = f"{prog}{arm} ({AY_CUR})"; home = f"Classroom {n}{arm}"
    for subj, per in ALLOC[stage].items():
        tc = [PRIMARY_TUTOR[prog]] if stage == "primary" and subj in TUTOR_SUBJECTS else TEACHERS[subj]
        units.append((g, g, prog, subj, per, tc, SPECIAL_ROOMS.get(subj, []) + [home]))
for g in groups.values():
    if g.group_based_on == "Course" and g.academic_year == AY_CUR:
        units.append((g.name, f"block-{g.program}", g.program, g.course, 3, TEACHERS[g.course],
                      SPECIAL_ROOMS.get(g.course, []) + SEMINAR))
units.sort(key=lambda u: (len(u[5]), -u[4]))
def build(seed):
    r = random.Random(seed)
    busy_t, busy_r, busy_g, load = set(), set(), set(), defaultdict(int)
    template, unplaced = [], 0
    for gname, gkey, prog, subj, per, tcands, rcands in units:
        teacher = min(tcands, key=lambda t: load[t]); load[teacher] += per
        days_used = set()
        for _ in range(per):
            opts = [s for s in SLOTS if (gname, s) not in busy_g and (gkey, s) not in busy_g
                    and (teacher, s) not in busy_t]
            pref = [s for s in opts if s[0] not in days_used] or opts
            r.shuffle(pref)
            for s in pref:
                room = next((x for x in rcands if (x, s) not in busy_r), None)
                if room:
                    busy_g.update({(gname, s), (gkey, s)}); busy_t.add((teacher, s)); busy_r.add((room, s))
                    days_used.add(s[0]); template.append((gname, prog, subj, teacher, room, s)); break
            else:
                unplaced += 1
    return unplaced, template, load
unplaced, template, load = min((build(sd) for sd in range(60)), key=lambda x: x[0])
term_days = school_days(TERMS[AY_CUR][0][1], TERMS[AY_CUR][0][2])
print(f"\n== TIMETABLE ==\n  weekly lessons placed {len(template)} (unplaced {unplaced}) | "
      f"term teaching days {len(term_days)} -> {len(template) * len(term_days) // 5} course schedules")
print("  teacher weekly loads:", dict(sorted(load.items(), key=lambda x: -x[1])))

# ---------------------------------------------------------------- attendance plan
profile = {}
all_students = {s for ms in members.values() for s, _ in ms}
for s in sorted(all_students):
    r = rng.random()
    profile[s] = 0.0 if r < 0.15 else (rng.uniform(0.12, 0.22) if r > 0.95 else rng.uniform(0.01, 0.06))
att_days = {AY_PREV: [d for _, a, b in TERMS[AY_PREV] for d in school_days(a, b)],
            AY_CUR: [d for d in term_days if d <= TODAY]}
print(f"\n== ATTENDANCE ==\n  school days: 2025-26 {len(att_days[AY_PREV])}, current term to date {len(att_days[AY_CUR])}")
print(f"  approx rows: {sum(len(members[g.name]) * len(att_days[ay]) for ay in att_days for g in batch_groups[ay])}")
print(f"  chronic absentees (>12%): {sum(1 for v in profile.values() if v > 0.12)} | perfect attendance: "
      f"{sum(1 for v in profile.values() if v == 0)}")

if not APPLY:
    frappe.destroy(); print("\nDry run complete."); raise SystemExit

# ---------------------------------------------------------------- 1. settings
print("\n== 1. Settings ==")
frappe.db.set_single_value("Education Settings", "attendance_based_on_course_schedule", 0)
frappe.db.commit()

# ---------------------------------------------------------------- 3. course schedules
print("== 3. Timetable (course schedules) ==")
already = frappe.db.count("Course Schedule", {"schedule_date": [">=", str(term_days[0])]})
if already:
    print(f"  {already} already exist, skipping")
else:
    color = {c: COLORS[i % len(COLORS)] for i, c in enumerate(sorted({t[2] for t in template}))}
    rows = []
    for d in term_days:
        for gname, prog, subj, teacher, room, (wd, p) in template:
            if wd != d.weekday(): continue
            rows.append({"student_group": gname, "instructor": ins_id.get(teacher), "instructor_name": teacher,
                         "program": prog, "course": subj, "room": room_id.get(room), "schedule_date": d,
                         "from_time": PERIODS[p][0], "to_time": PERIODS[p][1],
                         "class_schedule_color": color[subj], "title": f"{subj} by {teacher}"})
    attempt("Course schedules", lambda: bulk("Course Schedule", rows, "EDU-CSH-.YYYY.-"))

# ---------------------------------------------------------------- 4. leave applications
print("== 4. Leave applications ==")
leave_map = {}  # (student, date) -> (leave_app, mark_as_present)
if not frappe.db.count("Student Leave Application"):
    for ay, n_apps in ((AY_PREV, 30), (AY_CUR, 10)):
        days = att_days[ay]
        pool = [(g.name, s, nm) for g in batch_groups[ay] for s, nm in members[g.name]]
        for _ in range(n_apps):
            gname, s, nm = rng.choice(pool)
            i = rng.randrange(0, max(1, len(days) - 3)); ln = rng.choice([1, 1, 2, 2, 3])
            span = days[i:i + ln]
            if any((s, d) in leave_map for d in span): continue
            reason, mp = rng.choice(LEAVE_REASONS)
            doc = attempt(f"Leave {s}", lambda: ins({
                "doctype": "Student Leave Application", "student": s, "student_name": nm,
                "from_date": span[0], "to_date": span[-1], "reason": reason, "mark_as_present": mp,
                "attendance_based_on": "Student Group", "student_group": gname}, submit=True))
            if doc:
                for d in span: leave_map[(s, d)] = (doc.name, mp)
else:
    for la in frappe.get_all("Student Leave Application", filters={"docstatus": 1},
                             fields=["name", "student", "from_date", "to_date", "mark_as_present"]):
        d = la.from_date
        while d <= la.to_date:
            leave_map[(la.student, d)] = (la.name, la.mark_as_present); d += dt.timedelta(days=1)

# ---------------------------------------------------------------- 5. attendance
print("== 5. Attendance (bulk) ==")
existing = {(a.student, a.date) for a in frappe.get_all("Student Attendance", fields=["student", "date"],
                                                         limit_page_length=0)}
rows = []
for ay in (AY_PREV, AY_CUR):
    for g in batch_groups[ay]:
        for s, nm in members[g.name]:
            rate = profile.get(s, 0.03) * (rng.uniform(0.6, 1.3) if ay == AY_PREV else 1)
            streak = 0
            for d in att_days[ay]:
                if (s, d) in existing: continue
                if (s, d) in leave_map:
                    la, mp = leave_map[(s, d)]
                    status, link = ("Present" if mp else "Leave"), la
                else:
                    link = None
                    absent = (streak > 0 and rng.random() < 0.45) or rng.random() < rate
                    streak = streak + 1 if absent else 0
                    status = "Absent" if absent else "Present"
                rows.append({"student": s, "student_name": nm, "student_group": g.name, "date": d,
                             "status": status, "leave_application": link, "_docstatus": 1})
print(f"  inserting {len(rows)} rows")
attempt("Attendance", lambda: bulk("Student Attendance", rows, "EDU-ATT-.YYYY.-"))

# ---------------------------------------------------------------- 6. student logs
print("== 6. Student logs ==")
if not frappe.db.count("Student Log"):
    prog_courses = {p: [c.course for c in frappe.get_all("Program Course", filters={"parent": p}, fields=["course"])]
                    for p in {g.program for g in groups.values()}}
    for ay, n_logs in ((AY_PREV, 90), (AY_CUR, 45)):
        pool = [(g, s) for g in batch_groups[ay] for s, _ in members[g.name]]
        for _ in range(n_logs):
            g, s = rng.choice(pool)
            typ = rng.choices(list(LOGS), [35, 30, 20, 15])[0]
            text = rng.choice(LOGS[typ]).format(subj=rng.choice(prog_courses.get(g.program) or ["Mathematics"]))
            day = rng.choice(att_days[ay])
            term = next(t for t, a, b in TERMS[ay] if a <= day <= b)
            attempt(f"Log {s}", lambda: ins({"doctype": "Student Log", "student": s, "type": typ, "date": day,
                                             "academic_year": ay, "academic_term": term, "program": g.program,
                                             "student_batch": g.batch, "log": f"<p>{text}</p>"}))
    for s, v in profile.items():
        if v > 0.12:
            attempt(f"Log {s}", lambda s=s: ins({
                "doctype": "Student Log", "student": s, "type": "General", "date": TODAY,
                "academic_year": AY_CUR, "academic_term": TERMS[AY_CUR][0][0],
                "log": "<p>Attendance concern: absence rate above 12% this term. Meeting requested with parents.</p>"}))

# ---------------------------------------------------------------- 7. instructor teaching logs
print("== 7. Instructor teaching logs ==")
teacher_of, tlogs = {}, defaultdict(list)
for r in frappe.db.sql("""select instructor_name, program, course, student_group from `tabCourse Schedule`
        where instructor_name is not null group by instructor_name, program, course, student_group""", as_dict=True):
    tlogs[r.instructor_name].append((AY_CUR, TERMS[AY_CUR][0][0], r.program, r.course, r.student_group))
    teacher_of[(r.program, r.course)] = r.instructor_name
for g in batch_groups[AY_PREV]:   # last year: same teacher for the same subject and year group
    pes = frappe.get_all("Program Enrollment", filters={"student": ["in", [s for s, _ in members[g.name]]], "academic_year": AY_PREV, "docstatus": 1}, pluck="name")
    for c in sorted(set(frappe.get_all("Program Enrollment Course", filters={"parent": ["in", pes]}, pluck="course")) if pes else []):
        t = teacher_of.get((g.program, c))
        if t: tlogs[t].append((AY_PREV, None, g.program, c, g.name))
for person, rows in tlogs.items():
    ins_name = frappe.db.get_value("Instructor", {"instructor_name": person})
    if not ins_name: continue
    def save_logs(ins_name=ins_name, rows=rows):
        doc = frappe.get_doc("Instructor", ins_name)
        doc.set("instructor_log", [])
        for ay, term, prog, course, grp in sorted(rows, key=lambda x: (x[0], x[2], x[3])):
            doc.append("instructor_log", {"academic_year": ay, "academic_term": term, "department": doc.department,
                                          "program": prog, "course": course, "student_group": grp})
        doc.flags.ignore_permissions = True; doc.save()
    attempt(f"Instructor log {person}", save_logs)
print(f"  {sum(len(v) for v in tlogs.values())} log rows across {len(tlogs)} instructors")

# ---------------------------------------------------------------- verify
print("\n== VERIFY ==")
for d in ["Holiday", "Course Schedule", "Student Leave Application", "Student Attendance", "Student Log", "Instructor Log"]:
    print(f"  {d}: {frappe.db.count(d)}")
for ay in (AY_PREV, AY_CUR):
    names = [g.name for g in batch_groups[ay]]
    tot = frappe.db.count("Student Attendance", {"student_group": ["in", names]}) or 1
    pres = frappe.db.count("Student Attendance", {"student_group": ["in", names], "status": "Present"})
    print(f"  attendance {ay}: {tot} records, {pres * 100 / tot:.1f}% present")
print("  company holiday list:", frappe.db.get_value("Company", COMPANY, "default_holiday_list"))
print("  timezone:", frappe.db.get_single_value("System Settings", "time_zone"))
print("  created this run:", dict(created))
print(f"\nERRORS ({len(errors)}):" if errors else "\nNo errors.")
for x in errors[:30]: print("  ", x)
frappe.destroy()
