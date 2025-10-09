### Zanaverse Onboarding

Client onboarding with blueprints

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app zanaverse_onboarding
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/zanaverse_onboarding
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit


# Zanaverse Onboarding

Opinionated onboarding helpers for ERPNext/Frappe:
- Policy-driven Permission Query Conditions (PQC)
- Collaboration helpers (share Project on Task assignment)
- Project financial field privacy (permlevel-based)
- Blueprint/policy reconciliation

## What this app does

### 1) Policy-Driven PQC
- Scopes listing/linking by Company (and optionally Brand) using `User Permission` records.
- Controlled via `blueprints/policy.yaml -> pqc_doctypes`.
- You can disable PQC per doctype (e.g., `Project`) to keep OOTB behavior.

### 2) Collaboration on Task Assignment
- When a ToDo is created for a Task, we auto-grant Project access based on policy:
  - `collab.on_task_assignment: share_write` → creates/updates a **DocShare** (read+write).
  - `project_user` → adds the user to **Project User** child table.
  - `none` → do nothing.
- On ToDo trash, we downgrade/remove access if the user has no other assignments on the same Project.

### 3) Project Financial Field Privacy
- Moves selected Project fields to **permlevel 1** and grants **read** at that level to specific roles only.
- Controlled via `project_field_privacy` in `policy.yaml`.
- Idempotent and safe; re-run anytime.

## Key Policy Keys

```yaml
# blueprints/policy.yaml

strict_default_deny: true|false
pqc_bypass_roles:
  - System Manager

pqc_doctypes:
  "Lead": { enabled: true, company_field: company, brand_field: "" }
  "Project": { enabled: false, company_field: "", brand_field: "" } # OOTB visibility

collab:
  on_task_assignment: share_write   # share_write | project_user | none
  ignore_user_permissions_on_task_project: true

project_field_privacy:
  enabled: true
  permlevel: 1
  fields:
    - total_costing_amount
    - total_billed_amount
    - total_purchase_cost
    - total_expense_claim
    - gross_margin
    - per_gross_margin
    - margin
  level1_roles:
    - Accounts User
    - Accounts Manager
  strict_sync: true
  create_if_missing: true
