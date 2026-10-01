#!/bin/bash
# ZanaSchools demo pack: fills a school site (already set up from a school blueprint) with a full demo school.
# Usage (inside the backend container, from this folder):
#   bash run_demo.sh <site>            # dry run of every step (nothing written)
#   bash run_demo.sh <site> --apply    # build the demo school (~45-60 min); stops at the first step with errors
# NEVER run against a real school's production site.
set -u
SITE="${1:?usage: run_demo.sh <site> [--apply]}"
MODE="${2:-}"
PY=/home/frappe/frappe-bench/env/bin/python
cd "$(dirname "$0")"
export ZS_SITE="$SITE"
[ "$MODE" = "--apply" ] && export ZS_APPLY=1 || unset ZS_APPLY
LOG=/home/frappe/frappe-bench/logs/demo-pack-$(echo "$SITE" | tr . -)-$(date +%Y%m%d-%H%M).log
echo "demo pack -> $SITE ($([ "$MODE" = "--apply" ] && echo APPLY || echo DRY RUN)) | log: $LOG"
for step in 01_academic 02_people 03_daily 04_assessment 05a_structures 05b_invoices; do
  echo "=== $step ===" | tee -a "$LOG"
  $PY -u "$step.py" 2>&1 | grep -v RuntimeWarning | tee -a "$LOG" | tail -4
  if grep -q "ERRORS (\|PROBE FAILED\|Traceback" <(sed -n "/=== $step ===/,\$p" "$LOG"); then
    echo "!!! $step reported errors - stopping. See $LOG"; exit 1
  fi
  # dry runs of later steps need the earlier steps' data, so a dry run checks step 01 only
  [ "$MODE" != "--apply" ] && { echo "(dry run: later steps depend on 01's data; run with --apply to build)"; break; }
done
echo "=== DEMO PACK COMPLETE: $SITE ==="
