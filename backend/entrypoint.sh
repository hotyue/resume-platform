#!/bin/bash
set -e

echo "🔄 Running Alembic migrations..."
alembic -c /app/alembic.ini upgrade head

echo "✅ Migrations complete."

echo "📦 Importing templates..."
python /app/import_templates.py || echo "⚠️  Template import failed or skipped"

echo "✅ Template import done. Starting server..."
exec "$@"
