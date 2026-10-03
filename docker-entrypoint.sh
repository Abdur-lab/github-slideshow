#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import time

import sqlalchemy

from backend.config import Config

url = Config.SQLALCHEMY_DATABASE_URI
for attempt in range(30):
    try:
        engine = sqlalchemy.create_engine(url)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        print("Database is ready.")
        break
    except Exception as exc:
        print(f"Database not ready yet ({exc}); retrying...")
        time.sleep(1)
else:
    raise SystemExit("Database never became ready.")
PY

flask create-db
flask seed-db || true

exec "$@"
