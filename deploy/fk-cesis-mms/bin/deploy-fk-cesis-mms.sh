#!/usr/bin/env bash
set -euo pipefail

cd /opt/fk-cesis-mms

# Pull only app services during normal deploy; Postgres upgrades are deliberate ops tasks.
docker compose pull web qcluster
docker compose up -d --remove-orphans
