# ZanaSchools stack template (Frappe v16 + ERPNext + Education)

One stack serves **many school sites** (multi-site): gunicorn picks the site from the web address, nginx serves
each site's files from its own folder. Placeholders: `__STACK__` (e.g. zanaschools-prod), `__PRIMARY_HOST__`
(the first site's address), `__HOSTS__` (all addresses, comma-separated).

## Stand up a new stack
1. `mkdir /opt/frappe/<stack> && cd` there; copy these files; replace the placeholders (`sed -i`).
2. `cp env.example .env`, set values; `mkdir secrets` and write the DB root password to
   `secrets/mariadb_root_password.txt` (chmod 600). Never commit `.env` or `secrets/`.
3. Build the bench **at the path it runs from** (`/home/frappe/frappe-bench` inside the runtime image, mounted
   from `./frappe-bench`) — a bench built elsewhere and moved breaks every Python import.
   Apps: frappe, erpnext, education (version-16), zanaverse_config, zanaverse_onboarding, zanaverse_blueprints
   (on the bench only, never installed on a site).
4. `docker compose config` — read the resolved commands **before** every `up`/restart.
5. `docker compose up -d`; then add schools with the school blueprint + (for demos/twins only) the demo pack.

## Add a school to a running stack
`bench new-site <address> ...` → apply its blueprint → add the address to `VIRTUAL_HOST` in the frontend →
`docker compose up -d frontend`. (The front proxy, nginx-proxy, routes by VIRTUAL_HOST; an address must be
claimed by only one stack at a time.)

## Lessons baked in (each one cost us a debugging session)
- **gunicorn, not `bench serve`**: the dev server is single-site and single-threaded. Long container commands
  go on **one line in list form** — a multi-line YAML `>-` block keeps line breaks on more-indented lines and
  silently cuts the command ("No application module specified").
- **Healthcheck sends the site's Host header** — under gunicorn, `127.0.0.1` is not a site.
- **nginx `resolver 127.0.0.11` + backend address in a variable** — otherwise nginx caches the backend's IP and
  every backend restart gives a 502.
- **`location /files/` with `root .../sites/$host/public`** — gunicorn does not serve static files; without this
  rule every logo/upload 404s. Private files still go through Frappe (permission checks).
- **PDF downloads named `Fee-Invoice-<number>.pdf`** via the `download_pdf` location (`attachment` disposition).
- **Every site needs `host_name: https://<address>`** in site_config (the school blueprint sets it) — wkhtmltopdf
  fetches logos/CSS through it.
- **Container log limits**: set Docker's default (`/etc/docker/daemon.json`: json-file, max-size 10m, max-file 3)
  — unbounded logs grew to 4.4 GB on this server.
