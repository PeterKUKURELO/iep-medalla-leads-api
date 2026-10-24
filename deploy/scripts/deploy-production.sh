#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: deploy-production.sh DEPLOY_PATH COMMIT_SHA" >&2
  exit 2
fi

readonly deploy_path="$1"
readonly expected_sha="$2"

if [[ ! "$expected_sha" =~ ^[0-9a-f]{40,64}$ ]]; then
  echo "Invalid commit SHA" >&2
  exit 2
fi

cd "$deploy_path"

if [[ ! -f .env.production ]]; then
  echo "Missing protected .env.production in $deploy_path" >&2
  exit 1
fi

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Production checkout must remain on main" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Production has tracked local changes; refusing to overwrite them" >&2
  exit 1
fi

git fetch --quiet origin main
readonly remote_sha="$(git rev-parse origin/main)"

if [[ "$remote_sha" != "$expected_sha" ]]; then
  echo "Requested commit is not the current origin/main" >&2
  exit 1
fi

git merge --ff-only "$expected_sha"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing production virtual environment" >&2
  exit 1
fi

.venv/bin/python -m pip install --quiet .
.venv/bin/python -m pip check

APP_ENV=production .venv/bin/python - <<'PY'
from app.brands import get_brand_registry
from app.config import get_settings

get_settings()
get_brand_registry()
print("Production configuration is valid")
PY

APP_ENV=production .venv/bin/alembic upgrade head
sudo -n systemctl restart iep-medalla-leads-api
sudo -n systemctl is-active --quiet iep-medalla-leads-api

curl \
  --fail \
  --silent \
  --show-error \
  --retry 10 \
  --retry-all-errors \
  --retry-delay 2 \
  http://127.0.0.1:8000/health

echo
echo "Deployed $expected_sha"
