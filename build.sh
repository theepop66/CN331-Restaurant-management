#!/usr/bin/env bash
# Render build script: install deps, collect static files, migrate the database.
set -o errexit

pip install -r main/requirements.txt

cd main/myproject
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Optional: create an admin account for /admin/ (set DJANGO_SUPERUSER_PASSWORD on Render).
# `|| true` keeps the deploy green when the account already exists.
if [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --noinput \
    --username "${DJANGO_SUPERUSER_USERNAME:-admin}" \
    --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi

# Optional: load demo data (set SEED_DEMO=true on Render for the presentation).
if [ "${SEED_DEMO:-}" = "true" ]; then
  python manage.py seed_pos_demo
fi
