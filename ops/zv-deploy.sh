#!/usr/bin/env bash
# zv-deploy.sh - deploy every zanaverse_* app to EVERY site on one bench.
#
# Usage:  zv-deploy.sh <bench> [--dry-run] [--yes] [--with-files]
#   <bench>       folder under /opt/frappe: mtc-staging, mtc-prod, zanaschools-staging ...
#   --dry-run     preflight only (fetch, checks, incoming commits); changes nothing
#   --yes         skip the confirmation prompt
#   --with-files  include public/private files in the pre-deploy backups
#
# Steps: preflight -> backup all sites -> update repos -> pip/build changed apps
#        -> migrate every site -> apply each site's blueprint -> restart -> verify
# Run on the host as the frappe user. Log + state: <bench>/logs/deploy-<stamp>.{log,state}
set -euo pipefail   # no -E: ERR is handled once, at the top level

# This file lives in a repo the deploy updates, so run from a temporary copy.
if [[ -z "${ZV_DEPLOY_REEXEC:-}" ]]; then
  tmp=$(mktemp /tmp/zv-deploy.XXXXXX)
  cp "$0" "$tmp"
  ZV_DEPLOY_REEXEC="$tmp" exec bash "$tmp" "$@"
fi

BENCH="" DRY=0 YES=0 WITH_FILES=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --yes) YES=1 ;;
    --with-files) WITH_FILES="--with-files" ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) BENCH="$arg" ;;
  esac
done
[[ -n "$BENCH" ]] || { echo "Usage: zv-deploy.sh <bench> [--dry-run] [--yes] [--with-files]" >&2; exit 2; }

ROOT=/opt/frappe
BDIR="$ROOT/$BENCH"
FB="$BDIR/frappe-bench"
C="$BENCH"                                   # container prefix: <bench>-backend etc.
MIN_FREE_GB=5
[[ -d "$FB/apps" && -f "$FB/sites/apps.txt" ]] || { echo "No bench at $FB" >&2; exit 2; }

STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BDIR/logs"
LOG="$BDIR/logs/deploy-$STAMP.log"
STATE="$BDIR/logs/deploy-$STAMP.state"
exec > >(tee -a "$LOG") 2>&1

exec 9>"/tmp/zv-deploy-$BENCH.lock"
flock -n 9 || { echo "Another deploy is already running on $BENCH." >&2; exit 1; }

PHASE="preflight"
CHANGED=0
cleanup() { rm -f "${ZV_DEPLOY_REEXEC:-}"; }
on_error() {
  local rc=$? line=$1
  trap - ERR                                 # report once
  echo
  echo "!!!! FAILED during: $PHASE (line $line, exit $rc)"
  if (( CHANGED )); then
    echo "Code was already updated. To roll the code back:"
    while read -r kind a sha; do
      [[ "$kind" == repo ]] || continue
      echo "  git -C $FB/apps/$a reset --hard $sha"
      echo "  docker exec -w /home/frappe/frappe-bench $C-backend ./env/bin/pip install -q -e apps/$a"
    done < "$STATE"
    echo "  then migrate every site again and restart (RUNBOOK.md > Rollback)."
  elif [[ "$PHASE" == preflight ]]; then
    echo "Nothing was changed."
  else
    echo "Code was not changed (repos were already current)."
  fi
  [[ -f "$STATE" ]] && echo "Pre-deploy database backups are listed in $STATE"
  echo "Log: $LOG"
  exit "$rc"
}
trap 'on_error $LINENO' ERR
trap cleanup EXIT

hr()   { printf '\n==== %s\n' "$*"; }
be()   { docker exec -w /home/frappe/frappe-bench "$C-backend" "$@"; }
site() { local s=$1; shift; be bench --site "$s" "$@"; }
conf() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")' \
           "$FB/sites/$1/site_config.json" "$2"; }

# ---------------------------------------------------------------- preflight
hr "zv-deploy $BENCH  ($STAMP)$( ((DRY)) && echo '  DRY RUN')"
problems=()

[[ "$(docker inspect -f '{{.State.Running}}' "$C-backend" 2>/dev/null || true)" == "true" ]] \
  || problems+=("container $C-backend is not running")

free_gb=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
(( free_gb >= MIN_FREE_GB )) || problems+=("only ${free_gb}G free on / (need ${MIN_FREE_GB}G)")

mapfile -t SITES < <(for d in "$FB"/sites/*/; do [[ -f "$d/site_config.json" ]] && basename "$d"; done)
(( ${#SITES[@]} )) || problems+=("no sites found")

mapfile -t APPS < <(tr -d '\r' < "$FB/sites/apps.txt" | grep -E '^zanaverse_' || true)
for d in "$FB"/apps/zanaverse_*/; do
  a=$(basename "$d")
  printf '%s\n' "${APPS[@]}" | grep -qx "$a" || echo "  note: $a is on disk but not in apps.txt - skipped"
done

declare -A OLD NEW
hr "Repos"
for a in "${APPS[@]}"; do
  d="$FB/apps/$a"
  if [[ ! -d "$d/.git" ]]; then problems+=("$a: not a git repo"); continue; fi
  br=$(git -C "$d" symbolic-ref --short -q HEAD || true)
  if [[ -z "$br" ]]; then problems+=("$a: detached HEAD"); continue; fi
  # raw configured URLs (not insteadOf-rewritten): the remote that points at MarcTina92 on GitHub
  rm=$(git -C "$d" config --get-regexp '^remote\..*\.url$' | awk '$2 ~ /github\.com[:\/]MarcTina92\// {sub(/^remote\./,"",$1); sub(/\.url$/,"",$1); print $1; exit}')
  if [[ -z "$rm" ]]; then problems+=("$a: no MarcTina92 GitHub remote"); continue; fi
  if ! git -C "$d" fetch -q "$rm" "$br"; then problems+=("$a: fetch from $rm failed"); continue; fi
  dirty=$(git -C "$d" status --porcelain)
  [[ -z "$dirty" ]] || problems+=("$a: local changes (commit/push or discard first):"$'\n'"$(sed 's/^/        /' <<<"$dirty")")
  ahead=$(git -C "$d" rev-list --count "$rm/$br..HEAD")
  (( ahead == 0 )) || problems+=("$a: $ahead local commit(s) not pushed to $rm/$br")

  OLD[$a]=$(git -C "$d" rev-parse HEAD); NEW[$a]=$(git -C "$d" rev-parse "$rm/$br")
  incoming=$(git -C "$d" log --oneline "HEAD..$rm/$br" || true)
  printf '  %-22s %-10s %s -> %s  %s\n' "$a" "$br" "${OLD[$a]:0:7}" "${NEW[$a]:0:7}" \
    "$([[ -z "$incoming" ]] && echo '(up to date)' || echo "($(wc -l <<<"$incoming") incoming)")"
  [[ -z "$incoming" ]] || sed 's/^/        /' <<<"$incoming"
done

hr "Sites (${#SITES[@]})"
for s in "${SITES[@]}"; do
  bp=$(conf "$s" zanaverse_blueprint); env=$(conf "$s" zanaverse_environment)
  printf '  %-38s blueprint=%-12s env=%s\n' "$s" "${bp:--}" "${env:--}"
  [[ -n "$bp" ]] || echo "        WARN: no zanaverse_blueprint - blueprint step will be skipped"
  if [[ "$BENCH" == *-staging && -z "$env" ]]; then
    echo "        WARN: staging bench but zanaverse_environment not set"
  fi
done
echo "  disk free: ${free_gb}G"

if (( ${#problems[@]} )); then
  hr "STOPPED - fix these first (nothing was changed)"
  for p in "${problems[@]}"; do printf '  - %s\n' "$p"; done
  exit 1
fi
if (( DRY )); then hr "Dry run OK - nothing changed"; exit 0; fi

if (( ! YES )); then
  if [[ "$BENCH" == *-prod ]]; then
    read -r -p "PRODUCTION. Type the bench name ($BENCH) to deploy: " ans </dev/tty
    [[ "$ans" == "$BENCH" ]] || { echo "Cancelled."; exit 1; }
  else
    read -r -p "Deploy to $BENCH? [y/N] " ans </dev/tty
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 1; }
  fi
fi

# ---------------------------------------------------------------- backup
PHASE="backup"; hr "Backup ${#SITES[@]} site(s) ${WITH_FILES}"
for a in "${APPS[@]}"; do echo "repo $a ${OLD[$a]}" >> "$STATE"; done
for s in "${SITES[@]}"; do
  site "$s" backup $WITH_FILES >/dev/null
  f=$(ls -t "$FB/sites/$s/private/backups/"*-database.sql.gz 2>/dev/null | head -n1 || true)
  [[ -n "$f" ]] || { echo "No backup file found for $s"; false; }
  echo "backup $s $f" >> "$STATE"
  echo "  $s -> $(basename "$f") ($(du -h "$f" | cut -f1))"
done

# ---------------------------------------------------------------- update
PHASE="update repos"; hr "Update repos"
changed=(); build=()
for a in "${APPS[@]}"; do
  [[ "${OLD[$a]}" == "${NEW[$a]}" ]] && continue
  d="$FB/apps/$a"
  CHANGED=1
  git -C "$d" reset -q --hard "${NEW[$a]}"
  [[ "$(git -C "$d" rev-parse HEAD)" == "${NEW[$a]}" && -z "$(git -C "$d" status --porcelain)" ]] \
    || { echo "$a: working tree not clean after reset"; false; }
  changed+=("$a")
  if git -C "$d" diff --name-only "${OLD[$a]}" "${NEW[$a]}" | grep -q '/public/'; then build+=("$a"); fi
  echo "  $a -> ${NEW[$a]:0:7}"
done
(( ${#changed[@]} )) || echo "  all repos already current (migrate + blueprints still run on every site)"

PHASE="pip install"
for a in "${changed[@]}"; do echo "  pip install -e apps/$a"; be ./env/bin/pip install -q -e "apps/$a"; done
PHASE="build assets"
for a in "${build[@]}"; do hr "bench build --app $a"; be bench build --app "$a"; done

# ---------------------------------------------------------------- migrate
for s in "${SITES[@]}"; do
  PHASE="migrate $s"; hr "Migrate $s"
  # awk always exits 0, so with pipefail the pipeline fails exactly when migrate fails
  site "$s" migrate 2>&1 | awk '!/^(Updating DocTypes|Updating Dashboard|Updating customizations|Syncing)/'
done

# ---------------------------------------------------------------- blueprints
for s in "${SITES[@]}"; do
  PHASE="blueprint $s"
  bp=$(conf "$s" zanaverse_blueprint)
  if [[ -z "$bp" ]]; then hr "Blueprint $s: SKIPPED (no blueprint set)"; continue; fi
  hr "Blueprint $s ($bp)"
  out=$(site "$s" execute zanaverse_onboarding.blueprint_apply.apply 2>&1) || { echo "$out"; false; }
  grep -vE '^update ' <<<"$out" || true
  echo "  ($(grep -cE '^update ' <<<"$out" || true) records re-applied)"
  if grep -q 'Traceback' <<<"$out"; then echo "blueprint apply raised on $s"; false; fi
  site "$s" clear-cache
done

# ---------------------------------------------------------------- restart
PHASE="restart"; hr "Restart"
docker restart "$C-backend" "$C-worker-short" "$C-worker-long" "$C-scheduler" "$C-socketio" >/dev/null
for _ in $(seq 1 40); do
  [[ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' "$C-backend")" =~ ^(healthy|running)$ ]] && break
  sleep 3
done
sleep 5
echo "  $C-backend: $(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$C-backend")"

# ---------------------------------------------------------------- verify
PHASE="verify"; hr "Verify"
fail=0; warn=0
printf '  %-38s %-5s %-10s %s\n' SITE HTTP BLUEPRINT DOCTOR
for s in "${SITES[@]}"; do
  host=$(conf "$s" host_name); host=${host:-https://$s}
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${host%/}/login" || echo 000)
  bp=$(conf "$s" zanaverse_blueprint)
  if [[ -n "$bp" ]]; then
    dry=$(site "$s" execute zanaverse_onboarding.blueprint_apply.apply --kwargs "{'dry_run': True}" 2>&1 || true)
    drift=$(grep -cE '^(create|delete|setup) |Traceback' <<<"$dry" || true)
    bpres=$([[ "$drift" == 0 ]] && echo "in sync" || echo "DRIFT($drift)")
  else
    drift=0; bpres="none"
  fi
  if doc=$(site "$s" zv-doctor 2>&1); then docres="healthy"; else docres="ATTENTION"; warn=1; fi
  [[ "$code" == 200 && "$drift" == 0 ]] || fail=1
  [[ -n "$bp" ]] || warn=1
  printf '  %-38s %-5s %-10s %s\n' "$s" "$code" "$bpres" "$docres"
  [[ "$docres" == healthy ]] || grep -E '⚠️' <<<"$doc" | sed 's/^/        /' || true
  [[ "$drift" == 0 ]] || grep -E '^(create|delete|setup) |Traceback' <<<"$dry" | sed 's/^/        /' || true
done

hr "Result"
if (( fail )); then echo "  FAILED verification - see above. Backups + previous commits: $STATE"; exit 1; fi
(( warn )) && echo "  DEPLOYED with warnings (see above)" || echo "  DEPLOYED - all sites verified"
echo "  log: $LOG"
echo "  state (rollback info): $STATE"
