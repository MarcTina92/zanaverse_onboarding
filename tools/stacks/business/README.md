# Business stack (ERPNext, HR, CRM, Helpdesk, Insights, Wiki, telephony) - from mtc-prod

Captured from a running production stack, with names and addresses replaced by placeholders and no secrets.
Exact copies (secrets included) are in the nightly encrypted offsite backup (`zvcrypt:server-config/`).

## Placeholders
`__STACK__` stack/container prefix · `__PRIMARY_HOST__` first site address · `__HOST_2__` second site (business) ·
`__HOSTS__` all addresses, comma-separated · `__CERT_NAME__` the front proxy's certificate name

## Stand up a new stack
1. `mkdir /opt/frappe/<stack>`; copy these files; replace placeholders (`sed -i`).
2. `cp env.example .env` and set values (`chmod 600 .env`); write the DB root password to
   `secrets/mariadb_root_password.txt` (`chmod 600`, owned by the frappe user). Never commit `.env` or `secrets/`.
3. Note `docker-compose.override.yml`: Compose merges it automatically - it changes the stack. Read both files.
4. `docker compose config` before every `up`/restart; then `docker compose up -d`.
5. Add each site's address to `VIRTUAL_HOST`; set `host_name: https://<address>` on every site.
6. Check health: `bench --site all zv-doctor`.

## Already in this template
Container log limits (10 MB x 3); a `location /files/` rule serving each site's public files.

## Not yet (see tools/stacks/zanaschools/README.md for why each matters)
gunicorn as a one-line list command (if this stack still uses `bench serve`), nginx `resolver` + variable backend
address (no 502 after backend restarts).
