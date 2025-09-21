#!/usr/bin/env bash
set -euo pipefail
OUT_DIR=${BACKUP_DIR:-/var/backups/cricalgo}
mkdir -p "$OUT_DIR"
TS=$(date -u +%Y%m%dT%H%M%SZ)
PGDUMP=${PG_DUMP_CMD:-pg_dump}
DB_URL=${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/cricalgo}
F="$OUT_DIR/cricalgo_backup_$TS.sql.gz"
# create dump
pg_dump $DB_URL | gzip > "$F"
# rotate
find "$OUT_DIR" -type f -mtime +90 -delete
echo "Saved $F"
