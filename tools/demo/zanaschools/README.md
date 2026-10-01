# ZanaSchools demo pack

Fills a school site with a complete, realistic demo school — **Zana International School**: 178 students
from 8 African nationalities in 119 families, 21 staff, a clash-free timetable, a year and a term of
attendance, 14,345 assessment results, and fee invoices with realistic payment behaviour.

**A blueprint configures; a demo pack populates.** Use it for prospect demos, a school's staging/training
twin, and upgrade rehearsals. **Never run it against a real school's production site.**

## Prerequisites
A site set up from a school blueprint (company, accounts, fee categories, grading scales, criteria,
letterhead, invoice and report-card formats). For the demo school use the `zis` blueprint:
```bash
bench new-site <site> --install-app erpnext --install-app education --install-app zanaverse_config --install-app zanaverse_onboarding
bench --site <site> execute zanaverse_onboarding.blueprint_apply.apply --kwargs "{'name': 'zis'}"
```

## Run
From the host:
```bash
P=/home/frappe/frappe-bench/apps/zanaverse_onboarding/tools/demo/zanaschools
docker exec -w $P <stack>-backend bash run_demo.sh <site>            # dry run (step 01)
docker exec -w $P <stack>-backend bash run_demo.sh <site> --apply    # build (~45-60 min)
```
Every script can also run on its own: `ZS_SITE=<site> [ZS_APPLY=1] python <script>.py`
(dry run unless `ZS_APPLY=1`; safe to re-run — existing data is skipped).

| Step | Builds | Typical result |
|---|---|---|
| `01_academic` | Fiscal year 2025-26, academic years 2025-26 / 2026-27 / 2027-28, 7 terms, holiday calendar | 47 holidays + weekends |
| `02_people` | Programs, courses, rooms, houses, staff, departments, families, students, enrolments, groups, logins, applicants | 178 students, 312 enrolments, 41 groups, 9 logins |
| `03_daily` | Room names, Term 1 timetable, leave, attendance (last year + term to date), logs, teaching logs | ~4,545 lessons, ~26,600 attendance |
| `04_assessment` | Assessment group tree, plans, results (last year + term to date) | 1,266 plans, 14,345 results |
| `05a_structures` | Fee masters + 67 fee structures | |
| `05b_invoices` | Fee schedules → one Sales Invoice per student → payments | ~580 invoices + payments |

Data is **seeded**: the same school every time. Dates are relative to the calendar, so the current
term fills up to the day the pack is run.

## Demo logins (password `ZanaDemo#2026`, or `ZS_DEMO_PASSWORD`)
principal@ · deputy@ · bursar@ · registrar@ · teacher@ (Naledi Khumalo) — students dennis.otieno@,
chebet.kimani@ — parents akinyi.njoroge@, ama.agyeman@ — all `@zis.demo`.

## Files
`_common.py` shared helpers · `01`–`05b` the pack · `as-built/` the original scripts exactly as used to
build the first demo on staging (a record; `04` and `05a/b` were generated from them so every fix carries over).
