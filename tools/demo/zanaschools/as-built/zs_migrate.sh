#!/bin/bash
set -e
SITE=zanaschools-staging.zanaverse.com
cd /home/frappe/frappe-bench
[ -n "$ROOTPW" ] || { echo "ROOTPW is empty - stopping"; exit 1; }
echo "=== 1. new site ==="
bench new-site $SITE --db-root-password "$ROOTPW" --admin-password "$(openssl rand -hex 12)" --mariadb-user-host-login-scope="%"
[ -n "$ENC" ] && bench --site $SITE set-config encryption_key "$ENC"
echo "=== 2. restore golden backup (v15 data) ==="
bench --site $SITE restore golden.sql.gz --db-root-password "$ROOTPW" --force
echo "=== 3. migrate v15 -> v16 ==="
bench --site $SITE migrate
bench --site $SITE set-config mute_emails 1
bench use $SITE
echo "=== MIGRATE_DONE ==="
