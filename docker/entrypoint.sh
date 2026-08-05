#!/bin/sh
# Entrypoint for the library-verifier Docker image.
#
# Runs everything relative to /data, which callers are expected to mount as
# a volume (see README.md, "Docker (optional)"). This keeps the sqlite DB
# and the relative-path defaults of `db export`/`db dump` all landing in one
# externally-persisted place, without ever bind-mounting over /app (which
# would shadow the DSS jar/certs baked into the image at build time).
set -e
cd /data
exec uv run --project /app python /app/src/main.py \
    --db-path "${SBSEG_DB_PATH:-/data/signed_files.db}" "$@"
