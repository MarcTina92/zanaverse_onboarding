#!/usr/bin/env bash
set -euo pipefail

# Run from: ~/frappe-bench/apps/zanaverse_onboarding
REPO_ROOT="$(pwd)"
PKG_DIR="$REPO_ROOT/zanaverse_onboarding"

echo "Repo root: $REPO_ROOT"
test -d "$PKG_DIR" || { echo "❌ Missing package dir: $PKG_DIR"; exit 1; }

# 1) Flatten accidental extra nesting: zanaverse_onboarding/zanaverse_onboarding/
if [ -d "$PKG_DIR/zanaverse_onboarding" ]; then
  echo "→ Flattening extra nested package..."
  rsync -a --remove-source-files "$PKG_DIR/zanaverse_onboarding/" "$PKG_DIR/"
  find "$PKG_DIR/zanaverse_onboarding" -type d -empty -delete || true
fi

# 2) Ensure __init__.py and hooks.py exist
touch "$PKG_DIR/__init__.py"

if [ ! -f "$PKG_DIR/hooks.py" ]; then
  echo "→ Creating minimal hooks.py"
  cat > "$PKG_DIR/hooks.py" <<'PY'
app_name = "zanaverse_onboarding"
app_title = "Zanaverse Onboarding"
app_publisher = "MarcTina"
app_email = "support@zanaverse.com"
app_license = "MIT"
app_version = "0.1.0"

# Keep minimal; add other apps only if truly required at import time
required_apps = ["frappe"]

# Keep hooks light; do lazy imports inside handlers if needed.
PY
fi

# 3) Optional: ensure install.py has a safe after_install guard
if ! grep -q "def after_install" "$PKG_DIR/install.py" 2>/dev/null; then
  echo "→ Adding install.py with guarded after_install()"
  cat > "$PKG_DIR/install.py" <<'PY'
import os, frappe

def after_install():
    # Allow safe installs everywhere (skip heavy routines by env flag)
    if os.environ.get("ZV_SKIP_AFTER_INSTALL") == "1":
        frappe.logger().info("Skipping after_install (ZV_SKIP_AFTER_INSTALL=1)")
        return
    # Keep heavy provisioning out of hooks; put it in CLI callable functions.
PY
else
  if ! grep -q "ZV_SKIP_AFTER_INSTALL" "$PKG_DIR/install.py"; then
    echo "→ NOTE: Consider guarding after_install() with ZV_SKIP_AFTER_INSTALL env flag."
  fi
fi

# 4) Bulletproof assets: make sure public/ and build.json exist (with placeholders)
PUB_DIR="$PKG_DIR/public"
mkdir -p "$PUB_DIR/js" "$PUB_DIR/css"

[ -f "$PUB_DIR/js/placeholder.js" ] || echo '// placeholder' > "$PUB_DIR/js/placeholder.js"
[ -f "$PUB_DIR/css/placeholder.css" ] || echo '/* placeholder */' > "$PUB_DIR/css/placeholder.css"

cat > "$PUB_DIR/build.json" <<'JSON'
{
  "js/zanaverse_onboarding.bundle.js": [
    "public/js/placeholder.js"
  ],
  "css/zanaverse_onboarding.bundle.css": [
    "public/css/placeholder.css"
  ]
}
JSON

# 5) Quick sanity prints
echo "→ Package contents:"
ls -la "$PKG_DIR" | sed -n '1,200p'
echo "→ build.json:"
sed -n '1,200p' "$PUB_DIR/build.json"

# 6) Git commit & push
echo "→ Committing changes"
git add -A
git commit -m "chore: standardize layout; add safe public/build.json and placeholders; guard installs" || echo "No changes to commit."

# Pick your remote/branch if different
REMOTE="${1:-upstream}"
BRANCH="${2:-main}"

echo "→ Pushing to $REMOTE $BRANCH"
git push "$REMOTE" "$BRANCH"

echo "✅ Done. Now pull & rebuild on servers."
