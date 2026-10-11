# Zanaverse Runbook

How the Zanaverse platform is operated: deploys, new sites, rollback, and the gotchas we have hit.
Read this before any code, fixture, configuration or site change. No credentials are kept here.

## Platform model

- **A bench is a release group.** One Docker stack under `/opt/frappe/<bench>` runs one set of app versions and hosts many sites. Updates happen per bench, never per site: every deploy migrates **every** site on the bench.
- **Each site is separate at the data level:** its own database, `site_config.json`, installed apps and blueprint.
- **Configuration over code.** `zanaverse_config` is the platform app (features, switchable per site). `zanaverse_onboarding` is the provisioning engine. `zanaverse_blueprints` holds one folder per client (data only), extending `_base`. Client custom apps only by exception.
- **Staging first.** Every code, fixture, permission or configuration change is made and proven on a staging bench, committed and pushed, and reaches prod only through `zv-deploy.sh`. Record-level data (content, Insights configuration) may be changed directly where it lives.

### Benches (October 2026)

| Bench | Sites | Notes |
|---|---|---|
| `mtc-prod` | mtc, copperbloom, titan (`.zanaverse.com`) | Business clients, production |
| `mtc-staging` | mtc-staging, copperbloom-staging | Mirrors `mtc-prod` |
| `zanaschools-staging` | zanaschools-staging, zanaschools-demo | Schools stack (Education). No blueprints yet |
| `lms-prod` | learn.marctinaconsultancy.com | Stale (onboarding Nov 2025, config on `develop`); needs a catch-up before it can use `zv-deploy.sh` |

Planned: product-line release groups (`biz-prod`/`biz-staging`, `skool-prod`/`skool-staging`), each staging bench mirroring its prod bench.

Containers are named `<bench>-backend`, `-worker-short`, `-worker-long`, `-scheduler`, `-socketio`, `-frontend`, `-mariadb`, `-redis-*`. Each bench has its own MariaDB, reachable from the backend as `mariadb` (`db_host` is set in every bench's `common_site_config.json`).

## Deploying: `zv-deploy.sh`

The script lives in `zanaverse_onboarding/ops/zv-deploy.sh` and takes the bench as an argument, so any bench's copy can deploy any bench.

```bash
Z=/opt/frappe/mtc-staging/frappe-bench/apps/zanaverse_onboarding/ops/zv-deploy.sh
$Z mtc-staging --dry-run     # preflight only, changes nothing
$Z mtc-staging               # real deploy (asks y/N)
$Z mtc-prod --dry-run
$Z mtc-prod                  # asks you to type the bench name
```

Options: `--yes` skips the prompt, `--with-files` includes files in the backups.

**What it does, in order:**

1. **Preflight (no changes).** Fetches every `zanaverse_*` app listed in `apps.txt`. **Stops** if any repo has local changes, unpushed commits, a detached HEAD or a failed fetch; if under 5 GB disk is free; or if the backend is down. Shows incoming commits per repo, and each site's blueprint and environment flag.
2. **Backup** of every site (database; files with `--with-files`). Paths and the previous commit of every repo go into `<bench>/logs/deploy-<stamp>.state`.
3. **Update** each changed repo with `git reset --hard` to the remote branch, then checks the working tree is clean. `pip install -e` for changed apps; `bench build --app` only for apps whose `public/` files changed.
4. **Migrate every site**, stopping at the first failure.
5. **Apply each site's blueprint** (`zanaverse_blueprint` in `site_config.json`); sites without one are skipped with a warning. Then clear cache.
6. **Restart** backend, workers, scheduler and socketio; wait for health. About 30 seconds of downtime for every site on the bench.
7. **Verify each site:** HTTP 200 on `/login`; a blueprint dry run that must show no `create`/`delete`/`setup` (switches, permissions and workflow in place); `zv-doctor`.

Full output goes to `<bench>/logs/deploy-<stamp>.log`.

**Rules**

- Deploy staging first, then prod, from what is on GitHub. Commit and push from the staging checkout; the script refuses anything local.
- Run even when no code changed: it is also how every site gets migrated and its blueprint re-applied.
- Prod deploys at quiet times (early morning or weekend).
- Stock apps (frappe, erpnext, hrms, crm and so on) are **not** updated by the script. Upgrading them is a separate, planned exercise.

## Rollback

The `.state` file from the failed or unwanted deploy lists each repo's previous commit and each site's backup. The script prints these commands when it fails after changing code.

**Code (usual case):**

```bash
git -C /opt/frappe/<bench>/frappe-bench/apps/<app> reset --hard <previous sha>
docker exec -w /home/frappe/frappe-bench <bench>-backend ./env/bin/pip install -q -e apps/<app>
docker exec -w /home/frappe/frappe-bench <bench>-backend bench --site <site> migrate      # every site
docker restart <bench>-backend <bench>-worker-short <bench>-worker-long <bench>-scheduler <bench>-socketio
```

Do **not** run `zv-deploy.sh` afterwards: it would move the repos forward to GitHub again. Make the fix permanent with a `git revert` pushed to GitHub, then deploy normally.

**Database (only if a migrate or blueprint damaged data):**

```bash
docker exec -w /home/frappe/frappe-bench <bench>-backend bench --site <site> restore <backup .sql.gz from the state file>
```

It asks for the MariaDB root password. Where it lives differs per bench: prod uses `DB_ROOT_PASSWORD` in `<bench>/.env`; staging uses the Docker secret `/run/secrets/mariadb_root_password` in the mariadb container (the `.env` value there is wrong). Read it into a variable, never echo it.

## New client site

1. **Blueprint first (staging).** Add `zanaverse_blueprints/blueprints/<slug>/` extending `_base`: `sites`, `apps`, `company` (name, abbr, country, currency, timezone, financial year, first user) and `features`. Commit, push, deploy the staging bench.
2. **Create the site.** `db_host` comes from `common_site_config.json`; grant from any container address:
   ```bash
   cd /opt/frappe/<bench>
   DBPW=...   # see "Database" above for where it lives on this bench
   ADMINPW=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)
   docker exec -e DBPW="$DBPW" -e ADMINPW="$ADMINPW" -w /home/frappe/frappe-bench <bench>-backend sh -c '
   bench new-site <site> --db-root-password "$DBPW" --admin-password "$ADMINPW" --mariadb-user-host-login-scope="%" \
     --install-app erpnext --install-app hrms --install-app crm --install-app zanaverse_mail \
     --install-app zanaverse_config --install-app zanaverse_onboarding'
   echo "Administrator password (save in the password manager now): $ADMINPW"; unset DBPW ADMINPW
   ```
3. **Site config.** On staging benches also set the environment flag, which tells the engine to keep demo data:
   ```bash
   B="docker exec -w /home/frappe/frappe-bench <bench>-backend bench --site <site>"
   $B set-config zanaverse_blueprint <slug>
   $B set-config zanaverse_environment staging          # staging benches only
   $B set-config host_name "https://<site>"              # PDFs need it for logos/CSS
   ```
4. **Apply the blueprint** (dry run, then real). It runs the setup wizard, permissions, role profiles, feature switches, and back-dates scheduler jobs created before the timezone was set:
   ```bash
   $B execute zanaverse_onboarding.blueprint_apply.apply --kwargs "{'dry_run': True}"
   $B execute zanaverse_onboarding.blueprint_apply.apply
   ```
5. **Scheduler:** `$B enable-scheduler` **and** `$B scheduler resume` (new sites have a pause flag in `site_config.json`).
6. **Domain:** add the site to `VIRTUAL_HOST` in `<bench>/docker-compose.yml` (keep a backup copy first), then `docker compose up -d --no-deps frontend`. DNS goes through Cloudflare.
7. **Email:** until PR-02, client sites send through the shared `no-reply@zanaverse.com` account. When copying the Email Account from another site, **change its company link** to the new company.
8. **First user:**
   ```bash
   $B execute zanaverse_onboarding.blueprint_apply.add_user --kwargs "{'email': '...', 'first_name': '...', 'last_name': '...', 'role_profile': 'Client Administrator'}"
   ```
   The password reset is sent from the login page's **Forgot password** (in v16 there is no `User.reset_password()`).
9. **Check:** `$B zv-doctor` all ✅, then `zv-deploy.sh <bench> --dry-run` lists the site with its blueprint.

## Gotchas

**Git and deploys**
- Never `git reset --mixed` on a server. It moves HEAD but leaves the old files on disk, so the bench runs old code while git reports the new commit. The script uses `--hard` after checking for local changes.
- Remote names differ between checkouts (`origin` vs `upstream`); the script finds the MarcTina92 remote itself.
- Never commit the same change separately on two benches. Commit once on staging, push, and deploy.
- The server's GitHub token is fine-grained: a new repo must be added to its repository access, or fetch fails with "Write access to repository not granted" (403).
- Never `echo >> apps.txt`; check the trailing newline first.
- In an interactive shell, `!` inside double quotes triggers history expansion. Avoid `!!` in echo text.

**Frappe**
- Any Custom DocPerm row switches that doctype entirely to custom permissions. Every role needing access must have its own row.
- `frappe.get_all()` ignores permissions; `frappe.get_list()` applies them. Test as a user with `frappe.set_user(...)`.
- New `app_include_js` entries need `frappe.clear_cache()`; such files also need their `?v=N` bumped when they change.
- A long console session can hold a stale snapshot: `frappe.db.commit()` before trusting a result that contradicts the UI.
- In the console, wrap multi-line code in `exec('''...''', globals())`.
- `bench execute` prints a function's return value: functions that print their own report should not also return it.
- With developer mode on, migrate rewrites JSON files inside apps (seen on `mtc-staging` in `hrms`). Keep developer mode off outside active development.
- A bare `bench build --app crm` regenerates CRM bundles without branding; run a migrate afterwards. User-facing text says "ZanaCRM" / "ZanaERP".

**Infrastructure**
- The runtime is inside the containers; host-level Python or Node checks are misleading.
- Cloudflare caches static assets for a long time: purge, or bump a version parameter, after JS/CSS/HTML changes.
- MariaDB grants use wildcards (`%` or the subnet), never a single container IP.
- `frappe.db.exists` and `frappe.db.count` are case-insensitive; use `BINARY` for case-sensitive checks.
- The legacy `zanaverse_onboarding/blueprints/policy.yaml` is retired (permissions now come from `zanaverse_config` features plus blueprints). Copies removed in October 2026 are under `<bench>/legacy-backups/`.

**Wiki (wiki 3.0)**
- Every space needs explicit rows: Wiki User (Read) and Wiki Approver (Write); Guest only for deliberately public content. A space with no rows is readable by any logged-in account.
- Wiki Approvers must also hold Wiki User. The role picker doesn't list Wiki User: set rows with `wiki.api.wiki_space.update_space_roles` from the console.
- Retire a space by restricting it to Wiki Manager and unpublishing it.
