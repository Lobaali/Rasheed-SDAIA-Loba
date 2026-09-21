#!/usr/bin/env bash
set -e
docker compose up -d --build
START=$(date +%s)
until curl -fsS http://localhost:8000/v1/ready >/dev/null 2>&1; do
  sleep 0.2
done
END=$(date +%s)
echo "time-to-ready: $((END - START))s"