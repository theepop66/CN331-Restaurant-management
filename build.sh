#!/usr/bin/env bash
# Render build script: install deps, collect static files, migrate the database.
set -o errexit

pip install -r main/requirements.txt

cd main/myproject
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Optional: create an admin account for /admin/ (set DJANGO_SUPERUSER_PASSWORD on Render).
if [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py provision_deployment_admin
fi

# Optional: load demo data (set SEED_DEMO=true and DEMO_OWNER_PASSWORD).
if [ "${SEED_DEMO:-}" = "true" ]; then
  python manage.py seed_pos_demo
fi
